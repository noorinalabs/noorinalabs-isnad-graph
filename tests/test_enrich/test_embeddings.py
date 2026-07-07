"""Unit tests for semantic-search embedding enrichment (#1049).

All tests run without a live DB — the loader is exercised against mock Neo4j /
Postgres clients, and the embedder + helpers are pure functions. The full
staging embedding load is a cluster-internal step (P5W4); these tests prove the
mechanism, the idempotent upserts, and that the vector path is genuinely
exercised (≥1 embedded hadith) rather than mocked away.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock

import pytest

from src.enrich.embeddings import (
    DEFAULT_IVFFLAT_LISTS,
    EMBEDDING_DIM,
    HashingEmbedder,
    embedding_text,
    ensure_embedding_schema,
    fetch_hadiths_from_neo4j,
    get_embedder,
    reindex_embeddings,
    run_embedding_load,
    to_pgvector_literal,
    verify_recall,
)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# --- HashingEmbedder ----------------------------------------------------------


def test_hashing_embedder_dim_and_shape() -> None:
    emb = HashingEmbedder()
    vectors = emb.embed(["hello world", "another hadith text"])
    assert emb.dim == EMBEDDING_DIM
    assert len(vectors) == 2
    assert all(len(v) == EMBEDDING_DIM for v in vectors)


def test_hashing_embedder_is_deterministic() -> None:
    """Same text → identical vector across calls and instances (reproducible)."""
    a = HashingEmbedder().embed(["the prophet said"])[0]
    b = HashingEmbedder().embed(["the prophet said"])[0]
    assert a == b


def test_hashing_embedder_l2_normalised() -> None:
    [vec] = HashingEmbedder().embed(["prayer and fasting"])
    norm = math.sqrt(sum(x * x for x in vec))
    assert norm == pytest.approx(1.0)


def test_hashing_embedder_self_similarity_is_one() -> None:
    [vec] = HashingEmbedder().embed(["zakat charity"])
    assert _cosine(vec, vec) == pytest.approx(1.0)


def test_hashing_embedder_overlap_ranks_above_disjoint() -> None:
    """Token overlap yields higher cosine than a disjoint sentence — real signal."""
    emb = HashingEmbedder()
    query = emb.embed(["prayer is a pillar of faith"])[0]
    overlap = emb.embed(["prayer is obligatory in faith"])[0]
    disjoint = emb.embed(["zzz qqq xxx vvv"])[0]
    assert _cosine(query, overlap) > _cosine(query, disjoint)


def test_hashing_embedder_handles_arabic_tokens() -> None:
    [vec] = HashingEmbedder().embed(["إنما الأعمال بالنيات"])
    assert math.sqrt(sum(x * x for x in vec)) == pytest.approx(1.0)


def test_hashing_embedder_empty_text_is_zero_vector() -> None:
    [vec] = HashingEmbedder().embed([""])
    assert vec == [0.0] * EMBEDDING_DIM


def test_hashing_embedder_rejects_bad_dim() -> None:
    with pytest.raises(ValueError):
        HashingEmbedder(dim=0)


# --- helpers ------------------------------------------------------------------


def test_to_pgvector_literal_format() -> None:
    assert to_pgvector_literal([1.0, -0.5, 0.25]) == "[1.0,-0.5,0.25]"


def test_embedding_text_prefers_english() -> None:
    assert embedding_text("نص عربي", "english matn") == "english matn"


def test_embedding_text_falls_back_to_arabic() -> None:
    assert embedding_text("نص عربي", None) == "نص عربي"


def test_embedding_text_empty_when_neither() -> None:
    assert embedding_text(None, "   ") == ""


def test_get_embedder_defaults_to_hashing() -> None:
    get_embedder.cache_clear()
    emb = get_embedder("hashing")
    assert isinstance(emb, HashingEmbedder)
    assert emb.dim == EMBEDDING_DIM


# --- ensure_embedding_schema --------------------------------------------------


def test_ensure_embedding_schema_creates_tables_with_dim() -> None:
    pg = MagicMock()
    ensure_embedding_schema(pg, EMBEDDING_DIM)
    executed = " ".join(call.args[0] for call in pg.execute.call_args_list)
    assert "CREATE EXTENSION IF NOT EXISTS vector" in executed
    assert "isnad_graph.hadiths" in executed
    assert "isnad_graph.hadith_embeddings" in executed
    assert f"vector({EMBEDDING_DIM})" in executed
    assert "ivfflat" in executed


def test_ensure_embedding_schema_projects_facet_columns() -> None:
    """The hadiths projection carries the facet metadata, with an idempotent
    backfill for pre-existing tables (#1060)."""
    pg = MagicMock()
    ensure_embedding_schema(pg, EMBEDDING_DIM)
    executed = " ".join(call.args[0] for call in pg.execute.call_args_list)
    # Columns present in the CREATE TABLE for fresh installs.
    assert "collection_name text" in executed
    assert "topic_tags      text[]" in executed
    # Idempotent ADD COLUMN IF NOT EXISTS backfill for older deployments.
    assert "ALTER TABLE isnad_graph.hadiths" in executed
    assert "ADD COLUMN IF NOT EXISTS collection_name" in executed
    assert "ADD COLUMN IF NOT EXISTS topic_tags" in executed


def test_ensure_embedding_schema_rejects_non_int_dim() -> None:
    pg = MagicMock()
    with pytest.raises(ValueError):
        ensure_embedding_schema(pg, "384")  # type: ignore[arg-type]


# --- fetch_hadiths_from_neo4j -------------------------------------------------


def test_fetch_hadiths_applies_limit() -> None:
    neo4j = MagicMock()
    neo4j.execute_read.return_value = [{"id": "h1", "matn_ar": "a", "matn_en": "b"}]
    fetch_hadiths_from_neo4j(neo4j, limit=5)
    query, params = neo4j.execute_read.call_args.args
    assert "LIMIT $limit" in query
    assert params == {"limit": 5}


def test_fetch_hadiths_no_limit_passes_none() -> None:
    neo4j = MagicMock()
    neo4j.execute_read.return_value = []
    fetch_hadiths_from_neo4j(neo4j)
    query, params = neo4j.execute_read.call_args.args
    assert "LIMIT" not in query
    assert params is None


def test_fetch_hadiths_projects_facet_metadata() -> None:
    """The fetch query projects collection/grade/topics so they reach pgvector (#1060).

    ``grade`` resolves the connected Grading node with the same ``coalesce``
    fallback the full-text search route uses, keeping the two paths consistent.
    """
    neo4j = MagicMock()
    neo4j.execute_read.return_value = []
    fetch_hadiths_from_neo4j(neo4j)
    query = neo4j.execute_read.call_args.args[0]
    assert "collection_name AS collection_name" in query
    assert "topic_tags AS topic_tags" in query
    assert "GRADED_BY" in query
    assert "coalesce(g.grade, h.grade_composite, h.grade) AS grade" in query


def test_fetch_hadiths_no_scope_has_no_where_clause() -> None:
    """No scope arg = unchanged default: no WHERE, no collection params (#1177)."""
    neo4j = MagicMock()
    neo4j.execute_read.return_value = []
    fetch_hadiths_from_neo4j(neo4j)
    query, params = neo4j.execute_read.call_args.args
    assert "WHERE" not in query
    assert params is None


def test_fetch_hadiths_exclude_collections_adds_negated_where() -> None:
    """--exclude form filters in-query and binds the names as a param, not inline (#1177)."""
    neo4j = MagicMock()
    neo4j.execute_read.return_value = []
    fetch_hadiths_from_neo4j(neo4j, exclude_collections=["sanadset"])
    query, params = neo4j.execute_read.call_args.args
    assert "WHERE NOT h.collection_name IN $exclude_collections" in query
    # The filter precedes the OPTIONAL MATCH so it prunes before the join.
    assert query.index("WHERE") < query.index("OPTIONAL MATCH")
    assert params == {"exclude_collections": ["sanadset"]}
    # Collection names are parameterized, never string-interpolated into the query.
    assert "sanadset" not in query


def test_fetch_hadiths_include_collections_adds_allowlist_where() -> None:
    """--collections allowlist form filters in-query via a bound param (#1177)."""
    neo4j = MagicMock()
    neo4j.execute_read.return_value = []
    fetch_hadiths_from_neo4j(neo4j, include_collections=["bukhari", "muslim"])
    query, params = neo4j.execute_read.call_args.args
    assert "WHERE h.collection_name IN $include_collections" in query
    assert params == {"include_collections": ["bukhari", "muslim"]}
    assert "bukhari" not in query


def test_fetch_hadiths_scope_combines_with_limit() -> None:
    """Scope filter and limit coexist: WHERE prunes, LIMIT caps, both parameterized (#1177)."""
    neo4j = MagicMock()
    neo4j.execute_read.return_value = []
    fetch_hadiths_from_neo4j(neo4j, exclude_collections=["sanadset"], limit=10)
    query, params = neo4j.execute_read.call_args.args
    assert "WHERE NOT h.collection_name IN $exclude_collections" in query
    assert "LIMIT $limit" in query
    assert params == {"exclude_collections": ["sanadset"], "limit": 10}


def test_fetch_hadiths_rejects_both_scope_forms() -> None:
    """include + exclude together is ambiguous and rejected before any query runs (#1177)."""
    neo4j = MagicMock()
    with pytest.raises(ValueError, match="at most one"):
        fetch_hadiths_from_neo4j(
            neo4j, exclude_collections=["sanadset"], include_collections=["bukhari"]
        )
    neo4j.execute_read.assert_not_called()


# --- run_embedding_load (the mechanism, against mock clients) -----------------


def test_run_embedding_load_embeds_and_upserts() -> None:
    """End-to-end mechanism: hadiths mirrored + ≥1 real embedding upserted."""
    neo4j = MagicMock()
    neo4j.execute_read.return_value = [
        {"id": "h1", "matn_ar": "نص1", "matn_en": "first hadith"},
        {"id": "h2", "matn_ar": "نص2", "matn_en": "second hadith"},
    ]
    pg = MagicMock()

    result = run_embedding_load(neo4j, pg, embedder=HashingEmbedder(), batch_size=10)

    assert result.hadiths_loaded == 2
    assert result.embeddings_loaded == 2
    assert result.skipped_empty == 0
    assert result.dim == EMBEDDING_DIM
    assert result.model_name.startswith("hashing")

    # Two execute_many calls: hadiths upsert + embeddings upsert.
    upsert_sqls = [call.args[0] for call in pg.execute_many.call_args_list]
    assert any("INSERT INTO isnad_graph.hadiths" in sql for sql in upsert_sqls)
    assert any("INSERT INTO isnad_graph.hadith_embeddings" in sql for sql in upsert_sqls)
    # Every upsert is ON CONFLICT — re-running is idempotent.
    assert all("ON CONFLICT" in sql for sql in upsert_sqls)

    # The embedding rows carry a real pgvector literal (the vector path, not a mock).
    embedding_call = next(
        call for call in pg.execute_many.call_args_list if "hadith_embeddings" in call.args[0]
    )
    embedding_rows = embedding_call.args[1]
    assert len(embedding_rows) == 2
    hadith_id, source_text, vector_literal = embedding_rows[0]
    assert hadith_id == "h1"
    assert source_text == "first hadith"
    assert vector_literal.startswith("[") and vector_literal.endswith("]")


def test_run_embedding_load_threads_collection_scope_to_fetch() -> None:
    """Scope arg reaches the Neo4j read as a parameterized WHERE, not a Python filter (#1177)."""
    neo4j = MagicMock()
    neo4j.execute_read.return_value = []
    pg = MagicMock()

    run_embedding_load(neo4j, pg, embedder=HashingEmbedder(), exclude_collections=["sanadset"])

    query, params = neo4j.execute_read.call_args.args
    assert "WHERE NOT h.collection_name IN $exclude_collections" in query
    assert params == {"exclude_collections": ["sanadset"]}


def test_run_embedding_load_upserts_facet_metadata() -> None:
    """The hadiths upsert carries collection/grade/topics into the projection (#1060)."""
    neo4j = MagicMock()
    neo4j.execute_read.return_value = [
        {
            "id": "h1",
            "matn_ar": "نص",
            "matn_en": "a hadith",
            "collection_name": "Sahih al-Bukhari",
            "grade": "Sahih - Authentic",
            "topic_tags": ["intentions"],
        }
    ]
    pg = MagicMock()

    run_embedding_load(neo4j, pg, embedder=HashingEmbedder())

    hadith_call = next(
        call
        for call in pg.execute_many.call_args_list
        if "INSERT INTO isnad_graph.hadiths" in call.args[0]
    )
    sql, rows = hadith_call.args
    # The upsert lists and writes the facet columns.
    assert "collection_name" in sql
    assert "grade" in sql
    assert "topic_tags" in sql
    # The bound row carries the metadata through to the projection.
    (row,) = rows
    assert row == ("h1", "نص", "a hadith", "Sahih al-Bukhari", "Sahih - Authentic", ["intentions"])


def test_run_embedding_load_skips_textless_hadiths() -> None:
    neo4j = MagicMock()
    neo4j.execute_read.return_value = [
        {"id": "h1", "matn_ar": "نص", "matn_en": "has text"},
        {"id": "h2", "matn_ar": None, "matn_en": None},
    ]
    pg = MagicMock()

    result = run_embedding_load(neo4j, pg, embedder=HashingEmbedder())

    # Both hadiths mirrored to the metadata table; only the one with text embedded.
    assert result.hadiths_loaded == 2
    assert result.embeddings_loaded == 1
    assert result.skipped_empty == 1


def test_run_embedding_load_empty_corpus_is_noop() -> None:
    neo4j = MagicMock()
    neo4j.execute_read.return_value = []
    pg = MagicMock()

    result = run_embedding_load(neo4j, pg, embedder=HashingEmbedder())

    assert result.hadiths_loaded == 0
    assert result.embeddings_loaded == 0
    pg.execute_many.assert_not_called()


def test_run_embedding_load_batches() -> None:
    """Multiple batches each issue their own upserts (batch_size respected)."""
    neo4j = MagicMock()
    neo4j.execute_read.return_value = [
        {"id": f"h{i}", "matn_ar": f"ar{i}", "matn_en": f"en{i}"} for i in range(5)
    ]
    pg = MagicMock()

    result = run_embedding_load(neo4j, pg, embedder=HashingEmbedder(), batch_size=2)

    assert result.embeddings_loaded == 5
    # 3 batches (2 + 2 + 1) × 2 upserts each = 6 execute_many calls.
    assert pg.execute_many.call_count == 6


# --- reindex_embeddings (#1057) -----------------------------------------------


def test_reindex_builds_concurrently_then_atomic_swaps() -> None:
    """The rebuild never locks the live index: CONCURRENTLY build + atomic swap."""
    pg = MagicMock()
    result = reindex_embeddings(pg, lists=185)

    # The concurrent statements (which Postgres forbids inside a transaction) go
    # through the autocommit path, NOT a plain locking REINDEX.
    autocommit_sql = " ".join(call.args[0] for call in pg.execute_autocommit.call_args_list)
    assert "DROP INDEX CONCURRENTLY IF EXISTS isnad_graph.hadith_embeddings_embedding_idx_new" in (
        autocommit_sql
    )
    assert "CREATE INDEX CONCURRENTLY hadith_embeddings_embedding_idx_new" in autocommit_sql
    assert "WITH (lists = 185)" in autocommit_sql
    assert "REINDEX" not in autocommit_sql

    # The swap is a single transaction: drop the old index, rename the new one in.
    swap_queries = pg.execute_transaction.call_args.args[0]
    assert swap_queries == [
        "DROP INDEX IF EXISTS isnad_graph.hadith_embeddings_embedding_idx",
        "ALTER INDEX isnad_graph.hadith_embeddings_embedding_idx_new "
        "RENAME TO hadith_embeddings_embedding_idx",
    ]
    assert result.lists == 185
    assert result.index_name == "hadith_embeddings_embedding_idx"


def test_reindex_default_lists_is_tuned_for_corpus() -> None:
    """Default lists is ~sqrt(34028) ≈ 185, up from the schema's initial 100."""
    pg = MagicMock()
    result = reindex_embeddings(pg)
    assert result.lists == DEFAULT_IVFFLAT_LISTS == 185


def test_reindex_rejects_non_positive_lists() -> None:
    pg = MagicMock()
    with pytest.raises(ValueError):
        reindex_embeddings(pg, lists=0)


# --- verify_recall (#1088) ----------------------------------------------------


def _recall_pg(*, embeddings: int, embeddable: int, hits: list[dict[str, object]]) -> MagicMock:
    """A mock PgClient routing the count queries and the cosine search by SQL text."""
    pg = MagicMock()

    def _execute(query: str, params: object = None) -> list[dict[str, object]]:
        if "hadith_embeddings" in query and "JOIN" not in query and "count(*)" in query:
            return [{"n": embeddings}]
        if "FROM isnad_graph.hadiths" in query and "count(*)" in query:
            return [{"n": embeddable}]
        return hits  # the cosine search

    pg.execute.side_effect = _execute
    return pg


def test_verify_recall_passes_on_healthy_corpus() -> None:
    """Full table + topically-relevant top hits → pass, exit-code 0 territory."""
    hits = [
        {"matn_en": "Whoever prays with patience is rewarded", "matn_ar": "x", "score": 0.92},
        {"matn_en": "Prayer at dawn", "matn_ar": "y", "score": 0.80},
    ]
    pg = _recall_pg(embeddings=34028, embeddable=34028, hits=hits)

    result = verify_recall(pg, ["patience", "prayer"], embedder=HashingEmbedder())

    assert result.structural_ok is True
    assert result.passed is True
    assert [c.query for c in result.checks] == ["patience", "prayer"]
    assert all(c.passed for c in result.checks)


def test_verify_recall_fails_when_top_hits_off_topic() -> None:
    """Hits exist but none mention the topic → recall check fails."""
    hits = [{"matn_en": "unrelated text about trade", "matn_ar": "z", "score": 0.5}]
    pg = _recall_pg(embeddings=10, embeddable=10, hits=hits)

    result = verify_recall(pg, ["patience"], embedder=HashingEmbedder())

    assert result.structural_ok is True
    assert result.passed is False
    assert result.checks[0].keyword_matched is False


def test_verify_recall_fails_on_partial_load() -> None:
    """Embeddings count < embeddable hadiths → structural failure (partial load)."""
    hits = [{"matn_en": "patience is a virtue", "matn_ar": "z", "score": 0.9}]
    pg = _recall_pg(embeddings=9000, embeddable=34028, hits=hits)

    result = verify_recall(pg, ["patience"], embedder=HashingEmbedder())

    assert result.structural_ok is False
    assert result.passed is False


def test_verify_recall_fails_on_empty_results() -> None:
    """A query returning no rows fails (degenerate / empty index)."""
    pg = _recall_pg(embeddings=10, embeddable=10, hits=[])

    result = verify_recall(pg, ["prayer"], embedder=HashingEmbedder())

    assert result.passed is False
    assert result.checks[0].hits == 0
    assert result.checks[0].top_score == 0.0


def test_verify_recall_rejects_non_positive_top_k() -> None:
    pg = _recall_pg(embeddings=1, embeddable=1, hits=[])
    with pytest.raises(ValueError):
        verify_recall(pg, ["prayer"], top_k=0, embedder=HashingEmbedder())
