"""Hadith endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_neo4j
from src.api.models import HadithResponse, PaginatedResponse
from src.utils.neo4j_client import Neo4jClient

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


def _build_hadith_response(props: dict[str, Any]) -> HadithResponse:
    """Convert Neo4j properties dict into a HadithResponse with display_title."""
    hadith_id = props.get("id", "")
    collection_name = props.get("collection_name")
    display_title = _format_display_title(hadith_id, collection_name)

    return HadithResponse(
        id=hadith_id,
        matn_ar=props.get("matn_ar", ""),
        matn_en=props.get("matn_en"),
        isnad_raw_ar=props.get("isnad_raw_ar"),
        isnad_raw_en=props.get("isnad_raw_en"),
        grade_composite=props.get("grade_composite") or props.get("grade"),
        topic_tags=props.get("topic_tags", []),
        source_corpus=props.get("source_corpus", ""),
        collection_name=collection_name,
        display_title=display_title,
        has_shia_parallel=props.get("has_shia_parallel", False),
        has_sunni_parallel=props.get("has_sunni_parallel", False),
    )


@router.get("/hadiths", response_model=PaginatedResponse[HadithResponse])
def list_hadiths(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    collection: str | None = Query(None, description="Filter by collection name"),
    source_corpus: str | None = Query(None, description="Filter by source corpus"),
    grade: str | None = Query(None, description="Filter by grade"),
    q: str | None = Query(None, description="Search hadith text content"),
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
        where_clauses.append("(h.grade_composite = $grade OR h.grade = $grade)")
        params["grade"] = grade
    if q:
        where_clauses.append(
            "(toLower(h.matn_ar) CONTAINS toLower($q) OR toLower(h.matn_en) CONTAINS toLower($q))"
        )
        params["q"] = q

    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    count_query = f"MATCH (h:Hadith) {where} RETURN count(h) AS total"
    count_result = neo4j.execute_read(count_query, params)
    total = count_result[0]["total"] if count_result else 0

    data_query = (
        f"MATCH (h:Hadith) {where} "
        "RETURN properties(h) AS props ORDER BY h.id SKIP $skip LIMIT $limit"
    )
    rows = neo4j.execute_read(data_query, params)
    items = [_build_hadith_response(row["props"]) for row in rows]
    return PaginatedResponse(items=items, total=total, page=page, limit=limit)


@router.get("/hadiths/{hadith_id}", response_model=HadithResponse)
def get_hadith(
    hadith_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> HadithResponse:
    """Return a single hadith by ID."""
    rows = neo4j.execute_read(
        "MATCH (h:Hadith {id: $id}) RETURN properties(h) AS props",
        {"id": hadith_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Hadith '{hadith_id}' not found")
    return _build_hadith_response(rows[0]["props"])
