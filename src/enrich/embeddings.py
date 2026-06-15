"""Semantic-search embedding enrichment — compute hadith vectors and load pgvector.

This stage closes the gap behind isnad-graph#1049 ("semantic search returns
nothing — 0/34,028 hadiths have embeddings"). ``/search/semantic`` (see
``src/api/routes/search.py``) does a pgvector cosine match against
``isnad_graph.hadith_embeddings``; that table was never populated, so the
endpoint always returned empty. This module is the reproducible mechanism that
fills it.

Storage decision (the issue asks us to pick one and align both sides):
**pgvector in Postgres**, not ``h.embedding`` on Neo4j. The semantic endpoint
already targets ``isnad_graph.hadith_embeddings`` / ``isnad_graph.hadiths`` and
``PgClient.ensure_schema()`` already creates the ``vector`` extension, so
Postgres is the established home for vectors. The loader here writes there and
the endpoint reads from there — one backend, both sides aligned.

Embedder choice — why pluggable, dependency-free by default:
The default install carries **no heavy ML runtime**: ``torch`` /
``sentence-transformers`` are an *optional* extra (``[project.optional-dependencies]
ml``), so ``make setup`` (a bare ``uv sync``), CI, and the lean API image all stay
torch-free. The extra is installed only in the dedicated embed image
(``uv sync --extra ml`` — see the Dockerfile ``embed`` target) for the production
re-embed (#1071). So the embedder is a small :class:`Embedder` protocol with two
implementations:

* :class:`HashingEmbedder` — deterministic, pure-Python, zero-dependency. This is
  the default and the one CI / the sandbox exercise. It produces L2-normalised
  hashed bag-of-token vectors, so cosine similarity carries real lexical signal
  (the full vector path is genuinely exercised, not mocked) and results are
  perfectly reproducible.
* :class:`SentenceTransformerEmbedder` — lazily imports ``sentence_transformers``
  and is selected only when ``EMBEDDING_MODEL`` names a real model *and* the
  package is installed. This is the production / staging path
  (P5W4 cluster load), where a multilingual sentence-transformer gives true
  semantic similarity over the Arabic + English matn.

The dimension (:data:`EMBEDDING_DIM`, 384) matches the common multilingual
MiniLM family, so swapping the default for a real model in production needs an
env var, not a column migration.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Protocol

from src.config import get_settings
from src.models.enrich import (
    EmbeddingLoadResult,
    RecallCheck,
    RecallVerificationResult,
    ReindexEmbeddingsResult,
)
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.utils.neo4j_client import Neo4jClient
    from src.utils.pg_client import PgClient

__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_IVFFLAT_LISTS",
    "DEFAULT_RECALL_QUERIES",
    "EMBEDDING_DIM",
    "Embedder",
    "HashingEmbedder",
    "SentenceTransformerEmbedder",
    "embedding_text",
    "ensure_embedding_schema",
    "fetch_hadiths_from_neo4j",
    "get_embedder",
    "reindex_embeddings",
    "run_embedding_load",
    "to_pgvector_literal",
    "verify_recall",
]

log = get_logger(__name__)

# Vector dimension. 384 == sentence-transformers MiniLM family, so the default
# HashingEmbedder and a production multilingual MiniLM share a column type and a
# swap needs no migration. Changing this requires re-creating the embeddings
# table (the vector(N) type is fixed at DDL time).
EMBEDDING_DIM = 384

# Sentinel model name selecting the dependency-free hashing embedder.
HASHING_MODEL_NAME = "hashing"

DEFAULT_BATCH_SIZE = 256

# Canonical ivfflat index name (created by ``ensure_embedding_schema``) and the
# transient name a concurrent rebuild builds under before the atomic swap (#1057).
_CANONICAL_INDEX = "hadith_embeddings_embedding_idx"
_NEW_INDEX = "hadith_embeddings_embedding_idx_new"

# ivfflat ``lists`` for the rebuilt index. pgvector guidance is ~sqrt(rows) for
# rows up to ~1M; the corpus is ~34,028 hadiths, so sqrt(34028) ≈ 185 (up from
# the schema's initial 100, which was sized for a near-empty table). Overridable
# via ``isnad reindex-embeddings --lists N`` once the real row count is known.
DEFAULT_IVFFLAT_LISTS = 185

# Default known-topic queries for the recall smoke check / deploy gate (#1088).
DEFAULT_RECALL_QUERIES: tuple[str, ...] = ("patience", "prayer")

# Topical keywords accepted as evidence a query surfaced relevant hadiths. The
# corpus matn is English + Arabic (and the embedder prefers matn_en), so common
# English topic words plus their Arabic transliterations cover both the
# dependency-free hashing path (CI) and a real multilingual model (cluster). A
# query absent from this map falls back to matching its own lowercased token.
_RECALL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "patience": ("patience", "patient", "sabr", "persever", "endur"),
    "prayer": ("prayer", "pray", "salah", "salat", "worship"),
}

# Unicode-aware word tokenizer: ``\w+`` under ``re.UNICODE`` keeps Arabic letters
# as well as Latin/digits, so both matn_ar and matn_en contribute tokens.
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class Embedder(Protocol):
    """A text → fixed-dimension vector encoder.

    Implementations must be deterministic for a given text and return vectors of
    length :attr:`dim`. ``embed`` takes a batch so model-backed encoders can
    amortise per-call overhead.
    """

    @property
    def dim(self) -> int:
        """Dimension of every returned vector."""
        ...

    @property
    def model_name(self) -> str:
        """Human-readable identifier recorded with the load result."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Encode ``texts`` into a list of ``dim``-length float vectors."""
        ...


def _tokenize(text: str) -> list[str]:
    """Lowercase, Unicode-aware word tokens (Arabic + Latin + digits)."""
    return _TOKEN_RE.findall(text.lower())


class HashingEmbedder:
    """Deterministic, dependency-free hashing embedder (the CI/sandbox default).

    Each token is hashed to a bucket index and a sign via a stable digest
    (``blake2b``), accumulated into a fixed-width vector, then L2-normalised so
    cosine distance (pgvector ``<=>``) ranks by token overlap. No external
    dependency, no network, identical output across runs and machines.
    """

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        if dim <= 0:
            raise ValueError(f"dim must be positive, got {dim}")
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return f"{HASHING_MODEL_NAME}-{self._dim}"

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for token in _tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self._dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[bucket] += sign
        norm = math.sqrt(sum(component * component for component in vec))
        if norm > 0.0:
            vec = [component / norm for component in vec]
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]


class SentenceTransformerEmbedder:
    """Model-backed embedder for production (lazy ``sentence_transformers`` import).

    Selected only when ``EMBEDDING_MODEL`` names a real model and the optional
    ``sentence-transformers`` package is installed (the staging/production cluster,
    P5W4). Kept out of the default path so CI and the sandbox never need ``torch``.
    """

    def __init__(self, model_name: str, *, expected_dim: int = EMBEDDING_DIM) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - exercised only on the cluster
            raise RuntimeError(
                "sentence-transformers is not installed; install the optional ML "
                "extras or set EMBEDDING_MODEL=hashing for the dependency-free encoder."
            ) from exc

        self._model_name = model_name
        self._model = SentenceTransformer(model_name)
        reported_dim = int(self._model.get_sentence_embedding_dimension())
        if reported_dim != expected_dim:
            raise ValueError(
                f"model {model_name!r} produces dim={reported_dim}, but the "
                f"hadith_embeddings column is vector({expected_dim}). Set "
                f"EMBEDDING_DIM to match or pick a {expected_dim}-dim model."
            )
        self._dim = reported_dim

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - cluster only
        vectors = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=False)
        return [[float(component) for component in vector] for vector in vectors]


@lru_cache(maxsize=4)
def get_embedder(model_name: str | None = None) -> Embedder:
    """Return the configured embedder (cached so a model loads at most once).

    Resolution order: explicit ``model_name`` arg → ``EMBEDDING_MODEL`` setting →
    the dependency-free :class:`HashingEmbedder`. The cache means a heavy
    model-backed embedder is constructed once per process and reused by both the
    loader and the ``/search/semantic`` request path.
    """
    name = model_name or _configured_model_name()
    if name in (HASHING_MODEL_NAME, "", None):
        return HashingEmbedder(EMBEDDING_DIM)
    return SentenceTransformerEmbedder(name, expected_dim=EMBEDDING_DIM)


def _configured_model_name() -> str:
    """Read ``EMBEDDING_MODEL`` off settings, defaulting to the hashing sentinel."""
    return getattr(get_settings(), "embedding_model", HASHING_MODEL_NAME)


def to_pgvector_literal(vector: list[float]) -> str:
    """Render a vector as a pgvector text literal, e.g. ``[0.1,-0.2,0.3]``.

    Passed as a bound parameter cast with ``%s::vector`` so the value is never
    string-interpolated into SQL.
    """
    return "[" + ",".join(repr(component) for component in vector) + "]"


def embedding_text(matn_ar: str | None, matn_en: str | None) -> str:
    """Pick the text to embed for a hadith.

    Prefers the English matn (the semantic model's stronger language and the
    endpoint's display snippet), falling back to the Arabic matn. Returns an
    empty string when neither is present so the caller can skip it.
    """
    return (matn_en or matn_ar or "").strip()


# Projects the matn text plus the facet metadata the search page filters on
# (collection / grade / topic). ``grade`` resolves the connected Grading node and
# falls back to the legacy flat properties, mirroring the search route's
# ``_fulltext_hadith_search`` ``coalesce`` so the semantic path carries the same
# raw grade the fulltext path normalises (#1060). Mirroring this metadata into the
# pgvector-side ``isnad_graph.hadiths`` projection is what lets facets refine
# semantic results.
_FETCH_HADITHS_QUERY = """
MATCH (h:Hadith)
OPTIONAL MATCH (h)-[:GRADED_BY]->(g:Grading)
RETURN h.id AS id, h.matn_ar AS matn_ar, h.matn_en AS matn_en,
       h.collection_name AS collection_name,
       h.topic_tags AS topic_tags,
       coalesce(g.grade, h.grade_composite, h.grade) AS grade
"""


def fetch_hadiths_from_neo4j(
    neo4j: Neo4jClient, *, limit: int | None = None
) -> list[dict[str, Any]]:
    """Read matn text + facet metadata for every Hadith node (source of truth).

    Returns ``id``, ``matn_ar``, ``matn_en`` (the embedded/displayed text) plus
    ``collection_name``, ``grade``, and ``topic_tags`` — the facet metadata the
    search page filters on, projected here so it lands in pgvector alongside the
    embedding (#1060).
    """
    query = _FETCH_HADITHS_QUERY
    params: dict[str, int] = {}
    if limit is not None:
        query = query + "\nLIMIT $limit"
        params["limit"] = limit
    return neo4j.execute_read(query, params or None)


def ensure_embedding_schema(pg: PgClient, dim: int = EMBEDDING_DIM) -> None:
    """Create the schema, ``vector`` extension, and embedding tables (idempotent).

    ``dim`` is interpolated into the ``vector(N)`` type (a type, not a value, so it
    cannot be a bound parameter); it is validated as a positive int first so the
    interpolation is injection-safe.
    """
    if not isinstance(dim, int) or dim <= 0:
        raise ValueError(f"dim must be a positive int, got {dim!r}")
    pg.execute("CREATE SCHEMA IF NOT EXISTS isnad_graph")
    pg.execute("CREATE EXTENSION IF NOT EXISTS vector")
    pg.execute(
        """
        CREATE TABLE IF NOT EXISTS isnad_graph.hadiths (
            id              text PRIMARY KEY,
            matn_ar         text,
            matn_en         text,
            collection_name text,
            grade           text,
            topic_tags      text[]
        )
        """
    )
    # Backfill the facet columns on a pre-existing ``hadiths`` table (the
    # CREATE above is a no-op once the table exists). Idempotent, so re-running
    # the loader against an older deployment adds the metadata projection
    # without a separate migration (#1060).
    pg.execute(
        """
        ALTER TABLE isnad_graph.hadiths
            ADD COLUMN IF NOT EXISTS collection_name text,
            ADD COLUMN IF NOT EXISTS grade           text,
            ADD COLUMN IF NOT EXISTS topic_tags      text[]
        """
    )
    pg.execute(
        f"""
        CREATE TABLE IF NOT EXISTS isnad_graph.hadith_embeddings (
            hadith_id text PRIMARY KEY
                REFERENCES isnad_graph.hadiths (id) ON DELETE CASCADE,
            text      text,
            embedding vector({dim})
        )
        """
    )
    # ivfflat cosine index — matches the ``<=>`` operator the endpoint uses.
    pg.execute(
        """
        CREATE INDEX IF NOT EXISTS hadith_embeddings_embedding_idx
        ON isnad_graph.hadith_embeddings
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
        """
    )
    log.info("embedding_schema_ensured", dim=dim)


_UPSERT_HADITH_SQL = """
INSERT INTO isnad_graph.hadiths (id, matn_ar, matn_en, collection_name, grade, topic_tags)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE
SET matn_ar = EXCLUDED.matn_ar,
    matn_en = EXCLUDED.matn_en,
    collection_name = EXCLUDED.collection_name,
    grade = EXCLUDED.grade,
    topic_tags = EXCLUDED.topic_tags
"""

_UPSERT_EMBEDDING_SQL = """
INSERT INTO isnad_graph.hadith_embeddings (hadith_id, text, embedding)
VALUES (%s, %s, %s::vector)
ON CONFLICT (hadith_id) DO UPDATE
SET text = EXCLUDED.text, embedding = EXCLUDED.embedding
"""


def run_embedding_load(
    neo4j: Neo4jClient,
    pg: PgClient,
    *,
    embedder: Embedder | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    limit: int | None = None,
) -> EmbeddingLoadResult:
    """Compute hadith embeddings and load them into pgvector (idempotent).

    Reads Hadith nodes from Neo4j (the source of truth for matn text), mirrors
    ``(id, matn_ar, matn_en)`` into ``isnad_graph.hadiths`` and the computed
    vector into ``isnad_graph.hadith_embeddings``. Every write is an upsert, so
    re-running reconciles state rather than duplicating it. Hadiths with no matn
    text at all are skipped (nothing to embed).
    """
    active = embedder or get_embedder()
    ensure_embedding_schema(pg, active.dim)

    rows = fetch_hadiths_from_neo4j(neo4j, limit=limit)

    hadiths_loaded = 0
    embeddings_loaded = 0
    skipped_empty = 0

    for start in range(0, len(rows), batch_size):
        chunk = rows[start : start + batch_size]
        hadith_params: list[tuple[object, ...]] = []
        texts: list[str] = []
        embed_meta: list[tuple[str, str]] = []  # (hadith_id, source_text)

        for row in chunk:
            hadith_id = row["id"]
            if hadith_id is None:
                skipped_empty += 1
                continue
            text = embedding_text(row.get("matn_ar"), row.get("matn_en"))
            hadith_params.append(
                (
                    hadith_id,
                    row.get("matn_ar"),
                    row.get("matn_en"),
                    row.get("collection_name"),
                    row.get("grade"),
                    row.get("topic_tags"),
                )
            )
            if not text:
                skipped_empty += 1
                continue
            texts.append(text)
            embed_meta.append((hadith_id, text))

        if hadith_params:
            pg.execute_many(_UPSERT_HADITH_SQL, hadith_params)
            hadiths_loaded += len(hadith_params)

        if texts:
            vectors = active.embed(texts)
            embedding_params = [
                (hadith_id, source_text, to_pgvector_literal(vector))
                for (hadith_id, source_text), vector in zip(embed_meta, vectors, strict=True)
            ]
            pg.execute_many(_UPSERT_EMBEDDING_SQL, embedding_params)
            embeddings_loaded += len(embedding_params)

    result = EmbeddingLoadResult(
        hadiths_loaded=hadiths_loaded,
        embeddings_loaded=embeddings_loaded,
        skipped_empty=skipped_empty,
        model_name=active.model_name,
        dim=active.dim,
    )
    log.info(
        "embedding_load_complete",
        hadiths_seen=len(rows),
        hadiths_loaded=hadiths_loaded,
        embeddings_loaded=embeddings_loaded,
        skipped_empty=skipped_empty,
        model_name=active.model_name,
        dim=active.dim,
    )
    return result


def reindex_embeddings(
    pg: PgClient, *, lists: int = DEFAULT_IVFFLAT_LISTS
) -> ReindexEmbeddingsResult:
    """Rebuild the ivfflat cosine index with a tuned ``lists`` (idempotent) (#1057).

    After a bulk ``embed-hadiths`` load the ivfflat index should be rebuilt so its
    ``lists`` partition count matches the populated row count (a count chosen for a
    near-empty table gives poor recall once tens of thousands of rows land). This
    does it **without taking semantic search down**:

    1. ``CREATE INDEX CONCURRENTLY`` builds the new index while the live index
       keeps serving ``/search/semantic`` — no ``ACCESS EXCLUSIVE`` lock on it.
    2. An atomic swap (drop the old index, rename the new one to the canonical
       name, one transaction) flips queries onto the new index with no window in
       which neither index exists.

    Idempotent and safe to re-run: a leftover ``*_new`` index from a previously
    aborted build (which Postgres marks ``INVALID``) is dropped first, so a retry
    always starts clean. ``lists`` must be a positive int — it is interpolated
    into DDL (a value that cannot be a bound parameter), so it is validated to
    keep the interpolation injection-safe.
    """
    if not isinstance(lists, int) or lists <= 0:
        raise ValueError(f"lists must be a positive int, got {lists!r}")

    # Guarantee the table, extension, and a canonical index exist before we swap.
    ensure_embedding_schema(pg)

    # 1. Clear any INVALID leftover from a prior aborted concurrent build.
    pg.execute_autocommit(f"DROP INDEX CONCURRENTLY IF EXISTS isnad_graph.{_NEW_INDEX}")

    # 2. Build the replacement concurrently — the live index keeps serving reads.
    pg.execute_autocommit(
        f"CREATE INDEX CONCURRENTLY {_NEW_INDEX} "
        f"ON isnad_graph.hadith_embeddings "
        f"USING ivfflat (embedding vector_cosine_ops) WITH (lists = {lists})"
    )

    # 3. Atomic swap: drop the old index and rename the new one into its place.
    pg.execute_transaction(
        [
            f"DROP INDEX IF EXISTS isnad_graph.{_CANONICAL_INDEX}",
            f"ALTER INDEX isnad_graph.{_NEW_INDEX} RENAME TO {_CANONICAL_INDEX}",
        ]
    )

    log.info("embeddings_reindexed", lists=lists, index_name=_CANONICAL_INDEX)
    return ReindexEmbeddingsResult(lists=lists, index_name=_CANONICAL_INDEX)


_EMBEDDINGS_COUNT_SQL = "SELECT count(*) AS n FROM isnad_graph.hadith_embeddings"

# Hadiths that *should* carry an embedding: those with any matn text. Mirrors the
# loader's ``embedding_text`` skip rule (empty text → no vector), so equality with
# the embeddings count means every embeddable hadith was embedded.
_EMBEDDABLE_COUNT_SQL = (
    "SELECT count(*) AS n FROM isnad_graph.hadiths WHERE coalesce(matn_en, matn_ar, '') <> ''"
)

# Same cosine ranking the ``/search/semantic`` endpoint runs, so the gate exercises
# the real query path against the populated table.
_RECALL_SEARCH_SQL = """
SELECT h.matn_ar, h.matn_en,
       1 - (e.embedding <=> %s::vector) AS score
FROM isnad_graph.hadith_embeddings e
JOIN isnad_graph.hadiths h ON h.id = e.hadith_id
ORDER BY e.embedding <=> %s::vector
LIMIT %s
"""


def verify_recall(
    pg: PgClient,
    queries: Sequence[str] = DEFAULT_RECALL_QUERIES,
    *,
    top_k: int = 5,
    embedder: Embedder | None = None,
) -> RecallVerificationResult:
    """Smoke-check that semantic search returns topically relevant hits (#1088).

    This is the deploy workflow's verification gate after a re-embed: it proves
    the table is populated and the live query path surfaces on-topic hadiths,
    catching the failure modes a re-embed can leave behind — an empty/partial
    table, an all-zero/degenerate vector set, or a dimension mismatch.

    Two layers, both must pass for :attr:`RecallVerificationResult.passed`:

    * **Structural** — at least one embedding exists and the embedding count
      equals the number of hadiths with matn text (every embeddable hadith was
      embedded; not a partial load).
    * **Per-query topical** — each query is embedded and cosine-ranked exactly as
      the endpoint does; the check passes when it returns hits, the top hit has a
      strictly positive similarity, and at least one of the top-``k`` results'
      matn mentions a topic keyword (see :data:`_RECALL_KEYWORDS`).

    Read-only: it never writes, so it is safe to run against production.
    """
    if top_k <= 0:
        raise ValueError(f"top_k must be positive, got {top_k}")

    active = embedder or get_embedder()

    embeddings_count = int(pg.execute(_EMBEDDINGS_COUNT_SQL)[0]["n"])
    embeddable_count = int(pg.execute(_EMBEDDABLE_COUNT_SQL)[0]["n"])
    structural_ok = embeddings_count > 0 and embeddings_count == embeddable_count

    checks: list[RecallCheck] = []
    for query in queries:
        query_vector = to_pgvector_literal(active.embed([query])[0])
        rows = pg.execute(_RECALL_SEARCH_SQL, (query_vector, query_vector, top_k))
        top_score = float(rows[0]["score"]) if rows else 0.0
        haystack = " ".join(
            f"{row.get('matn_en') or ''} {row.get('matn_ar') or ''}" for row in rows
        ).lower()
        keywords = _RECALL_KEYWORDS.get(query.lower(), (query.lower(),))
        keyword_matched = any(keyword in haystack for keyword in keywords)
        passed = bool(rows) and top_score > 0.0 and keyword_matched
        checks.append(
            RecallCheck(
                query=query,
                hits=len(rows),
                top_score=top_score,
                keyword_matched=keyword_matched,
                passed=passed,
            )
        )

    passed = structural_ok and all(check.passed for check in checks)
    result = RecallVerificationResult(
        embeddings_count=embeddings_count,
        embeddable_count=embeddable_count,
        structural_ok=structural_ok,
        checks=checks,
        passed=passed,
    )
    log.info(
        "recall_verification_complete",
        embeddings_count=embeddings_count,
        embeddable_count=embeddable_count,
        structural_ok=structural_ok,
        passed=passed,
        model_name=active.model_name,
    )
    return result
