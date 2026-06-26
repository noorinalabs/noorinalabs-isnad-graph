"""CLI entry point for the isnad-graph platform."""

from __future__ import annotations

import argparse
import sys


def _mask_password(value: str) -> str:
    """Replace all but first and last character with asterisks."""
    if len(value) <= 2:
        return "*" * len(value)
    return value[0] + "*" * (len(value) - 2) + value[-1]


def _check_neo4j() -> None:
    """Pre-flight Neo4j connectivity check. Exits with code 1 on failure."""
    from neo4j import GraphDatabase

    from src.config import get_settings

    settings = get_settings()
    print("Checking Neo4j connectivity...")
    try:
        driver = GraphDatabase.driver(
            settings.neo4j.uri,
            auth=(settings.neo4j.user, settings.neo4j.password),
        )
        driver.verify_connectivity()
        driver.close()
    except Exception as exc:
        print(f"ERROR: Cannot connect to Neo4j at {settings.neo4j.uri}: {exc}")
        sys.exit(1)
    print("  Neo4j is reachable.")


def _cmd_info() -> None:
    """Print configuration (masked passwords) and check DB connectivity."""
    from src.config import get_settings

    settings = get_settings()

    print("=== isnad-graph configuration ===")
    print(f"  neo4j.uri      : {settings.neo4j.uri}")
    print(f"  neo4j.user     : {settings.neo4j.user}")
    print(f"  neo4j.password : {_mask_password(settings.neo4j.password)}")
    print(f"  postgres.dsn   : {settings.postgres.effective_dsn}")
    print(f"  redis.url      : {settings.redis.effective_url}")
    print(f"  log_level      : {settings.log_level}")
    print()

    # Neo4j connectivity check
    print("=== connectivity ===")
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.neo4j.uri,
            auth=(settings.neo4j.user, settings.neo4j.password),
        )
        driver.verify_connectivity()
        driver.close()
        print("  neo4j    : connected")
    except Exception:  # noqa: BLE001
        print("  neo4j    : unavailable")

    # PostgreSQL connectivity check
    try:
        import psycopg

        conn = psycopg.connect(settings.postgres.effective_dsn)
        conn.close()
        print("  postgres : connected")
    except Exception:  # noqa: BLE001
        print("  postgres : unavailable")


def _cmd_enrich_historical(dates_path: str | None = None) -> None:
    """Load HistoricalEvent nodes and link narrators by lifespan (ACTIVE_DURING).

    Closes the gap behind #965: without this stage the deployed graph has no
    HistoricalEvent nodes and the Timeline / Narrator Activity panel renders
    empty.

    When ``--dates`` is given, the resolved narrator date bounds + precision in
    that JSON file (the data-acquisition reconcile output, da#161-166) are written
    onto the matching Narrator nodes first, so ACTIVE_DURING windows use the real
    bounds rather than the death-anchored estimate (ig#1039).
    """
    _check_neo4j()

    from pathlib import Path

    from src.enrich.historical import load_narrator_dates_from_json, run_historical_overlay
    from src.utils.neo4j_client import Neo4jClient

    narrator_dates = None
    if dates_path is not None:
        narrator_dates = load_narrator_dates_from_json(Path(dates_path))
        print(f"Loaded {len(narrator_dates)} resolved narrator-date record(s) from {dates_path}")

    print("Running historical overlay (HistoricalEvent load + ACTIVE_DURING)...")
    with Neo4jClient() as client:
        result = run_historical_overlay(client, narrator_dates=narrator_dates)

    print("=== historical overlay complete ===")
    print(f"  events linked          : {result.events_linked}")
    print(f"  narrators dated        : {result.narrators_dated}")
    print(f"  narrators linked       : {result.narrators_linked}")
    print(f"  ACTIVE_DURING edges    : {result.edges_created}")
    print(f"  skipped (no dates)     : {result.narrators_skipped_no_dates}")
    print(f"  skipped (max lifetime) : {result.narrators_skipped_max_lifetime}")


def _cmd_embed_hadiths(batch_size: int, limit: int | None) -> None:
    """Compute hadith embeddings and load them into pgvector.

    Closes the gap behind #1049: with no embeddings loaded, ``/search/semantic``
    has nothing to cosine-match and always returns empty. This is the
    reproducible mechanism — re-running is idempotent (every write is an upsert).
    The embedding model is selected by ``EMBEDDING_MODEL`` (default ``hashing``,
    the dependency-free encoder; set a sentence-transformers model on the cluster
    for the production load).
    """
    _check_neo4j()

    from src.enrich.embeddings import get_embedder, run_embedding_load
    from src.utils.neo4j_client import Neo4jClient
    from src.utils.pg_client import PgClient

    embedder = get_embedder()
    print(f"Embedding hadiths (model={embedder.model_name}, dim={embedder.dim})...")
    with Neo4jClient() as neo4j, PgClient() as pg:
        result = run_embedding_load(
            neo4j, pg, embedder=embedder, batch_size=batch_size, limit=limit
        )

    print("=== embedding load complete ===")
    print(f"  hadiths loaded     : {result.hadiths_loaded}")
    print(f"  embeddings loaded  : {result.embeddings_loaded}")
    print(f"  skipped (no matn)  : {result.skipped_empty}")
    print(f"  model              : {result.model_name}")
    print(f"  dim                : {result.dim}")


def _cmd_reindex_embeddings(lists: int) -> None:
    """Rebuild the ivfflat semantic-search index with a tuned ``lists`` count.

    Closes #1057. Run after a bulk ``embed-hadiths`` load so the index partitions
    match the populated row count. Uses ``CREATE INDEX CONCURRENTLY`` + an atomic
    swap, so ``/search/semantic`` keeps serving throughout (no ``REINDEX`` lock on
    the live index). Idempotent — safe to re-run.
    """
    from src.enrich.embeddings import reindex_embeddings
    from src.utils.pg_client import PgClient

    print(f"Rebuilding ivfflat index (lists={lists}) with CONCURRENTLY + atomic swap...")
    with PgClient() as pg:
        result = reindex_embeddings(pg, lists=lists)

    print("=== reindex complete ===")
    print(f"  index : {result.index_name}")
    print(f"  lists : {result.lists}")


def _cmd_verify_recall(queries: list[str], top_k: int) -> int:
    """Verify semantic search returns topically relevant hits; return an exit code.

    Closes #1088. This is the deploy workflow's verification gate after a
    re-embed: it asserts the embeddings table is fully populated and that each
    known query surfaces on-topic hadiths. Returns 0 on pass, 1 on failure.
    """
    from src.enrich.embeddings import get_embedder, verify_recall
    from src.utils.pg_client import PgClient

    embedder = get_embedder()
    print(
        f"Verifying recall (model={embedder.model_name}, queries={','.join(queries)}, "
        f"top_k={top_k})..."
    )
    with PgClient() as pg:
        result = verify_recall(pg, queries, top_k=top_k, embedder=embedder)

    print("=== recall verification ===")
    print(f"  embeddings loaded  : {result.embeddings_count}")
    print(f"  embeddable hadiths : {result.embeddable_count}")
    print(f"  structural ok      : {result.structural_ok}")
    for check in result.checks:
        status = "PASS" if check.passed else "FAIL"
        print(
            f"  [{status}] {check.query!r}: hits={check.hits} "
            f"top_score={check.top_score:.4f} keyword={check.keyword_matched}"
        )
    print(f"  overall            : {'PASS' if result.passed else 'FAIL'}")
    return 0 if result.passed else 1


def main() -> None:
    """Run the isnad-graph CLI."""
    parser = argparse.ArgumentParser(description="isnad-graph: Hadith Analysis Platform")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("info", help="Show configuration and database status")
    historical_parser = subparsers.add_parser(
        "enrich-historical",
        help="Load HistoricalEvent nodes and link narrators (ACTIVE_DURING)",
    )
    historical_parser.add_argument(
        "--dates",
        type=str,
        default=None,
        help=(
            "Optional path to a JSON array of resolved narrator-date records "
            "(da#161-166) to write onto Narrator nodes before linking."
        ),
    )
    embed_parser = subparsers.add_parser(
        "embed-hadiths",
        help="Compute hadith embeddings and load them into pgvector (semantic search)",
    )
    embed_parser.add_argument(
        "--batch-size", type=int, default=256, help="Embedding/upsert batch size (default 256)"
    )
    embed_parser.add_argument(
        "--limit", type=int, default=None, help="Only embed the first N hadiths (default: all)"
    )
    reindex_parser = subparsers.add_parser(
        "reindex-embeddings",
        help="Rebuild the ivfflat semantic-search index (CONCURRENTLY, no downtime)",
    )
    reindex_parser.add_argument(
        "--lists",
        type=int,
        default=185,
        help="ivfflat lists (index partitions); ~sqrt(rows). Default 185 for ~34k hadiths.",
    )
    verify_parser = subparsers.add_parser(
        "verify-recall",
        help="Assert semantic search returns topically relevant hits (exit code = gate)",
    )
    verify_parser.add_argument(
        "--queries",
        type=str,
        default="patience,prayer",
        help="Comma-separated known queries to check (default: patience,prayer)",
    )
    verify_parser.add_argument(
        "--top-k", type=int, default=5, help="Top-K results inspected per query (default 5)"
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "info":
        _cmd_info()
    elif args.command == "enrich-historical":
        _cmd_enrich_historical(args.dates)
    elif args.command == "embed-hadiths":
        _cmd_embed_hadiths(args.batch_size, args.limit)
    elif args.command == "reindex-embeddings":
        _cmd_reindex_embeddings(args.lists)
    elif args.command == "verify-recall":
        queries = [q.strip() for q in args.queries.split(",") if q.strip()]
        sys.exit(_cmd_verify_recall(queries, args.top_k))


if __name__ == "__main__":
    main()
