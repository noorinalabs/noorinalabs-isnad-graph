"""Hadith endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_neo4j
from src.api.models import HadithFacetsResponse, HadithResponse, PaginatedResponse, TopicFacet
from src.utils.grades import GRADE_TOKENS, grade_filter_clause, normalize_grade
from src.utils.neo4j_client import Neo4jClient
from src.utils.topics import aggregate_topic_facets

# Cypher expression for the effective raw grade: prefer the traversed Grading node,
# fall back to any legacy flat property on the Hadith node.
_GRADE_EXPR = "coalesce(g.grade, h.grade_composite, h.grade)"

router = APIRouter()

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


@router.get("/hadiths/facets", response_model=HadithFacetsResponse)
def get_hadith_facets(
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> HadithFacetsResponse:
    """Return distinct facet values for filtering hadiths."""
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
    # Topic facet: pull every hadith's raw topic_tags (including those with none)
    # and aggregate onto the canonical vocabulary. Scanning all hadiths is what
    # lets the uncategorized bucket count tag-less documents rather than dropping
    # them; the per-hadith payload is just a small string list. (#1061)
    topic_rows = neo4j.execute_read("MATCH (h:Hadith) RETURN h.topic_tags AS topic_tags")
    topics = [
        TopicFacet(value=fc.value, label=fc.label, count=fc.count)
        for fc in aggregate_topic_facets([row.get("topic_tags") for row in topic_rows])
    ]
    return HadithFacetsResponse(
        source_corpus=[row["corpus"] for row in rows],
        grades=sorted(GRADE_TOKENS),
        topics=topics,
    )


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
