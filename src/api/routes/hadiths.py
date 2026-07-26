"""Hadith endpoints."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_neo4j
from src.api.models import (
    HadithDatingResponse,
    HadithFacetsResponse,
    HadithResponse,
    NarratorWindow,
    PaginatedResponse,
    TopicFacet,
)
from src.utils.grades import GRADE_TOKENS, grade_filter_clause, normalize_grade
from src.utils.neo4j_client import Neo4jClient
from src.utils.redis_client import get_redis_client
from src.utils.topics import aggregate_topic_facets_from_counts

# Cypher expression for the effective raw grade: prefer the traversed Grading node,
# fall back to any legacy flat property on the Hadith node.
_GRADE_EXPR = "coalesce(g.grade, h.grade_composite, h.grade)"

router = APIRouter()

# Mirror of ``src.enrich.historical.DEFAULT_ASSUMED_LIFESPAN_AH``. Kept as a
# module constant (rather than importing the enrich layer into the API layer,
# matching ``validate.py``) so the API has no dependency on the enrichment
# pipeline; the value is a stable domain assumption, not a tuning knob.
DEFAULT_ASSUMED_LIFESPAN_AH = 80


# Mapping from corpus/collection slug to human-readable name
_COLLECTION_DISPLAY_NAMES: dict[str, str] = {
    "bukhari": "Sahih al-Bukhari",
    "muslim": "Sahih Muslim",
    "abu_dawud": "Sunan Abu Dawud",
    "abudawud": "Sunan Abu Dawud",
    "tirmidhi": "Jami' al-Tirmidhi",
    "nasai": "Sunan al-Nasa'i",
    "ibn_majah": "Sunan Ibn Majah",
    "ibnmajah": "Sunan Ibn Majah",
    "malik": "Muwatta Malik",
    "darimi": "Sunan al-Darimi",
    "ahmad": "Musnad Ahmad",
    "nawawi": "40 Hadith Nawawi",
    "qudsi": "Hadith Qudsi",
    "riyadussalihin": "Riyad al-Salihin",
    "adab": "Al-Adab al-Mufrad",
    "bulugh": "Bulugh al-Maram",
    "mishkat": "Mishkat al-Masabih",
    "al_kafi": "Al-Kafi",
    "al-kafi": "Al-Kafi",
    "man_la_yahduruhu_al_faqih": "Man La Yahduruhu al-Faqih",
    "tahdhib_al_ahkam": "Tahdhib al-Ahkam",
    "al_istibsar": "Al-Istibsar",
}


def _format_display_title(hadith_id: str, collection_name: str | None) -> str:
    """Build a human-readable title from the hadith ID and collection name.

    ID format: hdt:{corpus}:{collection}:{book}:{hadith}
    or shorter variants like hdt:{corpus}:{collection}:{hadith}.
    """
    parts = hadith_id.split(":")
    # parts[0] = "hdt", parts[1] = corpus, parts[2] = collection, ...
    if len(parts) < 3:
        return hadith_id

    collection_slug = parts[2] if len(parts) > 2 else ""
    # Use collection_name from Neo4j if available, else try mapping, else titleize slug
    display_name = (
        collection_name
        or _COLLECTION_DISPLAY_NAMES.get(collection_slug)
        or collection_slug.replace("_", " ").title()
    )

    if len(parts) >= 5:
        # hdt:corpus:collection:book:hadith
        return f"{display_name} {parts[3]}:{parts[4]}"
    if len(parts) == 4:
        # hdt:corpus:collection:hadith
        return f"{display_name}, Hadith {parts[3]}"
    return display_name


def _build_hadith_response(props: dict[str, Any], grade: str | None = None) -> HadithResponse:
    """Convert Neo4j properties dict into a HadithResponse with display_title.

    ``grade`` is the raw grade text resolved via the ``GRADED_BY`` traversal; it
    falls back to a legacy flat ``grade_composite``/``grade`` property on the Hadith
    node when no Grading node is connected. The raw text is surfaced for display and
    its canonical form is exposed as ``grade_normalized`` for filtering/colouring.
    """
    hadith_id = props.get("id", "")
    collection_name = props.get("collection_name")
    display_title = _format_display_title(hadith_id, collection_name)

    raw_grade = grade or props.get("grade_composite") or props.get("grade")

    return HadithResponse(
        id=hadith_id,
        matn_ar=props.get("matn_ar", ""),
        matn_en=props.get("matn_en"),
        isnad_raw_ar=props.get("isnad_raw_ar"),
        isnad_raw_en=props.get("isnad_raw_en"),
        grade_composite=raw_grade,
        grade_normalized=normalize_grade(raw_grade),
        topic_tags=props.get("topic_tags", []),
        source_corpus=props.get("source_corpus", ""),
        collection_name=collection_name,
        display_title=display_title,
        has_shia_parallel=props.get("has_shia_parallel", False),
        has_sunni_parallel=props.get("has_sunni_parallel", False),
    )


# Redis cache for the hadith facets response. The facets are a whole-corpus
# aggregation that only changes when the graph is (re)loaded, but the endpoint is
# hit on every HadithsPage mount — so it is cached under a short TTL rather than
# recomputed per request. The key carries a version suffix so a change to the
# response shape / vocabulary invalidates stale entries on deploy without needing
# an explicit reload signal; the TTL bounds staleness after a data reload. Redis
# is best-effort (see :func:`_facets_cache_get`), so this never hard-depends on
# the cache being reachable.
_FACETS_CACHE_KEY = "hadith:facets:v1"
_FACETS_CACHE_TTL_SECONDS = 300


def _facets_cache_get(cache: Any | None) -> HadithFacetsResponse | None:
    """Return the cached facets response, or ``None`` on miss / unreachable Redis.

    Every Redis interaction is best-effort: a connection error or an
    incompatible (stale-shape) cached payload degrades to a cache miss so the
    request is served by recomputing, never by failing.
    """
    if cache is None:
        return None
    try:
        raw = cache.get(_FACETS_CACHE_KEY)
    except Exception:  # noqa: BLE001 — cache is best-effort, never fail the request
        return None
    if not raw:
        return None
    try:
        return HadithFacetsResponse.model_validate_json(raw)
    except Exception:  # noqa: BLE001 — ignore a stale/incompatible cache entry
        return None


def _facets_cache_set(cache: Any | None, response: HadithFacetsResponse) -> None:
    """Store the facets response under a short TTL; best-effort (never raises)."""
    if cache is None:
        return
    try:
        cache.setex(_FACETS_CACHE_KEY, _FACETS_CACHE_TTL_SECONDS, response.model_dump_json())
    except Exception:  # noqa: BLE001 — a cache write failure must not fail the request
        return


def _compute_hadith_facets(neo4j: Neo4jClient) -> HadithFacetsResponse:
    """Compute the hadith facets straight from Neo4j (cache-independent)."""
    rows = neo4j.execute_read(
        "MATCH (h:Hadith) WHERE h.source_corpus IS NOT NULL "
        "RETURN DISTINCT h.source_corpus AS corpus ORDER BY corpus"
    )
    # The grade facet exposes the full canonical grade vocabulary — the single
    # source of truth in ``src.utils.grades`` — rather than only the tokens that
    # happen to be present in the loaded corpus. Deriving it from live ``Grading``
    # nodes silently dropped valid grades whenever the data was sparse: e.g.
    # ``munkar``/``shadh``/``hasan_sahih`` were unreachable in the UI even though
    # the filter (:func:`grade_filter_clause`) fully supports them (#1062). Every
    # token here filters correctly via the ``?grade=`` param on the list endpoint.
    # Topic facet: aggregate topic_tags in Cypher — ``count(*)`` grouped by the
    # distinct ``topic_tags`` value — instead of streaming one row per hadith
    # (~870k over Bolt on every request; #1191). Grouping by the raw list keeps
    # the canonical mapping + uncategorized-bucket semantics exactly (a hadith's
    # topics depend only on its ``topic_tags`` value, which is the grouping key),
    # so tag-less hadiths still land in ``uncategorized`` and multi-tag hadiths
    # aren't double-counted (#1061). NULL/absent ``topic_tags`` form their own
    # group and fall through to the uncategorized bucket.
    topic_rows = neo4j.execute_read(
        "MATCH (h:Hadith) RETURN h.topic_tags AS topic_tags, count(*) AS n"
    )
    topics = [
        TopicFacet(value=fc.value, label=fc.label, count=fc.count)
        for fc in aggregate_topic_facets_from_counts(
            (row.get("topic_tags"), row.get("n", 1)) for row in topic_rows
        )
    ]
    return HadithFacetsResponse(
        source_corpus=[row["corpus"] for row in rows],
        grades=sorted(GRADE_TOKENS),
        topics=topics,
    )


@router.get("/hadiths/facets", response_model=HadithFacetsResponse)
def get_hadith_facets(
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> HadithFacetsResponse:
    """Return distinct facet values for filtering hadiths.

    Served from a short-TTL Redis cache when available (the facets are a
    whole-corpus aggregation that only changes on a data reload); on a cache
    miss or when Redis is unreachable the facets are computed directly and the
    result is written back best-effort. The endpoint never hard-depends on
    Redis, mirroring the rate limiter's graceful fallback.
    """
    cache = get_redis_client()
    cached = _facets_cache_get(cache)
    if cached is not None:
        return cached

    response = _compute_hadith_facets(neo4j)
    _facets_cache_set(cache, response)
    return response


@router.get("/hadiths", response_model=PaginatedResponse[HadithResponse])
def list_hadiths(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    collection: str | None = Query(None, description="Filter by collection name"),
    source_corpus: str | None = Query(None, description="Filter by source corpus"),
    grade: str | None = Query(None, description="Filter by grade"),
    q: str | None = Query(None, description="Search hadith text content"),
    narrator: str | None = Query(
        None, description="Filter to hadiths whose isnad contains this narrator (id)"
    ),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> PaginatedResponse[HadithResponse]:
    """Return a paginated list of hadiths with optional filters."""
    skip = (page - 1) * limit

    where_clauses: list[str] = []
    params: dict[str, Any] = {"skip": skip, "limit": limit}

    if collection:
        where_clauses.append("h.collection_name = $collection")
        params["collection"] = collection
    if source_corpus:
        where_clauses.append("h.source_corpus = $source_corpus")
        params["source_corpus"] = source_corpus
    if grade:
        # Match the connected Grading node's (or legacy flat) grade against the
        # requested canonical token, using the same rules as normalize_grade.
        clause, grade_params = grade_filter_clause(grade, _GRADE_EXPR)
        where_clauses.append(clause)
        params.update(grade_params)
    if q:
        where_clauses.append(
            "(toLower(h.matn_ar) CONTAINS toLower($q) OR toLower(h.matn_en) CONTAINS toLower($q))"
        )
        params["q"] = q
    if narrator:
        # A narrator is "in the isnad" of hadith h when they either directly
        # NARRATED h, or are an endpoint of one of h's TRANSMITTED_TO edges
        # (those edges carry hadith_id — the per-hadith chain lives on the
        # edge properties, not on Chain nodes; see #1032). The existential
        # subqueries keep the outer count(h)/properties(h) query a simple scan.
        where_clauses.append(
            "(EXISTS { MATCH (na:Narrator {id: $narrator})-[:NARRATED]->(h) } "
            "OR EXISTS { MATCH (na:Narrator {id: $narrator})-[t:TRANSMITTED_TO]-(:Narrator) "
            "WHERE t.hadith_id = h.id })"
        )
        params["narrator"] = narrator

    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # OPTIONAL MATCH so ungraded hadiths still list; when a grade filter is active
    # its clause requires g, so the OPTIONAL MATCH then effectively inner-joins.
    # Grading is 1:1 per hadith, so this does not duplicate rows.
    base = f"MATCH (h:Hadith) OPTIONAL MATCH (h)-[:GRADED_BY]->(g:Grading) {where} "

    count_query = f"{base}RETURN count(h) AS total"
    count_result = neo4j.execute_read(count_query, params)
    total = count_result[0]["total"] if count_result else 0

    data_query = (
        f"{base}RETURN properties(h) AS props, {_GRADE_EXPR} AS grade "
        "ORDER BY h.id SKIP $skip LIMIT $limit"
    )
    rows = neo4j.execute_read(data_query, params)
    items = [_build_hadith_response(row["props"], row.get("grade")) for row in rows]
    return PaginatedResponse(items=items, total=total, page=page, limit=limit)


@router.get("/hadiths/{hadith_id}", response_model=HadithResponse)
def get_hadith(
    hadith_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> HadithResponse:
    """Return a single hadith by ID."""
    rows = neo4j.execute_read(
        "MATCH (h:Hadith {id: $id}) "
        "OPTIONAL MATCH (h)-[:GRADED_BY]->(g:Grading) "
        f"RETURN properties(h) AS props, {_GRADE_EXPR} AS grade",
        {"id": hadith_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Hadith '{hadith_id}' not found")
    return _build_hadith_response(rows[0]["props"], rows[0].get("grade"))


def _dating_window(
    birth_year_ah: int | None,
    birth_year_ah_earliest: int | None,
    death_year_ah: int | None,
    death_year_ah_latest: int | None,
    assumed_lifespan_ah: int,
) -> tuple[tuple[int, int] | None, bool, bool]:
    """Resolve a narrator's ``[start, end]`` active window for hadith dating.

    Mirrors :func:`src.enrich.historical._active_window`: prefers the resolved
    *outer* bounds (``birth_year_ah_earliest`` / ``death_year_ah_latest``,
    ig#1039) so the window widens to earliest-plausible-birth .. latest-plausible
    -death, and falls back to the point estimates with the death-attested /
    birth-estimated asymmetry (death-only -> ``[death - lifespan, death]``,
    birth-only -> ``[birth, birth + lifespan]``).

    Returns ``(window, estimated, end_estimated)``. ``estimated`` is True when an
    assumed-lifespan span filled *either* endpoint (surfaced on the narrator's
    :class:`NarratorWindow`). ``end_estimated`` is True only when the window *end*
    (the death anchor that fixes a terminus) was itself estimated -- so a
    death-attested / birth-estimated narrator, the common case, has an attested
    terminus anchor even though its window start is a guess. ``window`` is
    ``None`` when the narrator carries no year in any form.
    """
    eff_birth = birth_year_ah_earliest if birth_year_ah_earliest is not None else birth_year_ah
    eff_death = death_year_ah_latest if death_year_ah_latest is not None else death_year_ah
    if eff_birth is None and eff_death is None:
        return None, True, True
    if eff_death is None:
        # Birth-only: the END is the assumed-lifespan extrapolation.
        assert eff_birth is not None
        return (eff_birth, eff_birth + assumed_lifespan_ah), True, True
    if eff_birth is None:
        # Death-only (the norm): the END (death) is attested; only the start guessed.
        return (eff_death - assumed_lifespan_ah, eff_death), True, False
    return (eff_birth, eff_death), False, False


def _dating_narrator_window(entry: tuple[dict[str, Any], int, int, bool, bool]) -> NarratorWindow:
    """Build a :class:`NarratorWindow` from a resolved chain-narrator entry."""
    row, start, end, estimated, _end_estimated = entry
    return NarratorWindow(
        narrator_id=row["id"],
        name_ar=row.get("name_ar"),
        name_en=row.get("name_en"),
        birth_year_ah=row.get("birth_year_ah"),
        death_year_ah=row.get("death_year_ah"),
        window_start_ah=start,
        window_end_ah=end,
        estimated=estimated,
    )


def derive_hadith_dating(
    hadith_id: str,
    narrators: list[dict[str, Any]],
    *,
    assumed_lifespan_ah: int = DEFAULT_ASSUMED_LIFESPAN_AH,
) -> HadithDatingResponse:
    """Derive a hadith's dating window from its chain narrators (pure, DB-free).

    Each narrator's active window is resolved (:func:`_dating_window`) and the two
    termini are anchored on the window *end* (death): the earliest death fixes the
    ``terminus_post_quem`` (content attested from this era) and the latest death
    the ``terminus_ante_quem`` (isnad fully transmitted by then). Undated/partial
    chains degrade to an ``insufficient_data`` window rather than raising.
    """
    windows: list[tuple[dict[str, Any], int, int, bool, bool]] = []
    for row in narrators:
        window, estimated, end_estimated = _dating_window(
            row.get("birth_year_ah"),
            row.get("birth_year_ah_earliest"),
            row.get("death_year_ah"),
            row.get("death_year_ah_latest"),
            assumed_lifespan_ah,
        )
        if window is None:
            continue
        windows.append((row, window[0], window[1], estimated, end_estimated))

    chain_count = len(narrators)
    dated_count = len(windows)

    if dated_count == 0:
        note = (
            "Insufficient data: no narrator in this hadith's isnad chain carries a "
            "resolvable birth or death year, so a dating window cannot be derived."
            if chain_count
            else "Insufficient data: this hadith has no reconstructable isnad chain."
        )
        return HadithDatingResponse(
            hadith_id=hadith_id,
            confidence="insufficient_data",
            chain_narrator_count=chain_count,
            dated_narrator_count=0,
            assumed_lifespan_ah=assumed_lifespan_ah,
            note=note,
        )

    earliest = min(windows, key=lambda w: w[2])
    latest = max(windows, key=lambda w: w[2])
    tpq = earliest[2]
    taq = latest[2]

    confidence: Literal["high", "medium", "low"]
    if dated_count == 1:
        # Span collapses to a single point -- a weak, single-narrator anchor.
        confidence = "low"
    elif earliest[4] or latest[4]:
        # A terminus anchor (a window END) rests on an assumed-lifespan estimate
        # rather than an attested death year.
        confidence = "medium"
    elif dated_count == chain_count:
        confidence = "high"
    else:
        confidence = "medium"

    note = (
        f"Chain resolves to AH {tpq}-{taq} ({confidence} confidence) "
        f"from {dated_count} of {chain_count} dated narrators."
    )

    return HadithDatingResponse(
        hadith_id=hadith_id,
        terminus_post_quem_ah=tpq,
        terminus_ante_quem_ah=taq,
        chain_span_ah=taq - tpq,
        confidence=confidence,
        chain_narrator_count=chain_count,
        dated_narrator_count=dated_count,
        earliest_narrator=_dating_narrator_window(earliest),
        latest_narrator=_dating_narrator_window(latest),
        assumed_lifespan_ah=assumed_lifespan_ah,
        note=note,
    )


@router.get("/hadiths/{hadith_id}/dating", response_model=HadithDatingResponse)
def get_hadith_dating(
    hadith_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> HadithDatingResponse:
    """Return a chain-derived dating window for a hadith (ig#1042).

    The window is computed from the resolved active windows (ig#1039) of the
    narrators in the hadith's isnad chain -- the direct ``NARRATED`` narrator plus
    the endpoints of the hadith's per-chain ``TRANSMITTED_TO`` edges (there are no
    reified ``Chain`` nodes; #1032). See :class:`HadithDatingResponse` for the
    terminus semantics. A hadith with an undated or partial chain returns an
    ``insufficient_data`` window with a clear ``note`` -- never a 500.
    """
    exists = neo4j.execute_read(
        "MATCH (h:Hadith {id: $id}) RETURN h.id AS id",
        {"id": hadith_id},
    )
    if not exists:
        raise HTTPException(status_code=404, detail=f"Hadith '{hadith_id}' not found")

    # The chain's narrators are those directly NARRATED-linked to the hadith or
    # sitting on one of its per-hadith TRANSMITTED_TO edges (undirected, so both
    # endpoints are collected). DISTINCT de-duplicates a narrator reached by both
    # paths. Only the date props _dating_window reads are projected.
    rows = neo4j.execute_read(
        """
        CALL {
            MATCH (n:Narrator)-[:NARRATED]->(:Hadith {id: $id})
            RETURN n
            UNION
            MATCH (n:Narrator)-[:TRANSMITTED_TO {hadith_id: $id}]-(:Narrator)
            RETURN n
        }
        WITH DISTINCT n
        RETURN n.id AS id, n.name_ar AS name_ar, n.name_en AS name_en,
               n.birth_year_ah AS birth_year_ah,
               n.birth_year_ah_earliest AS birth_year_ah_earliest,
               n.death_year_ah AS death_year_ah,
               n.death_year_ah_latest AS death_year_ah_latest
        ORDER BY n.id
        """,
        {"id": hadith_id},
    )
    return derive_hadith_dating(hadith_id, rows)
