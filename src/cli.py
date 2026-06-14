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


def _cmd_enrich_historical() -> None:
    """Load HistoricalEvent nodes and link narrators by lifespan (ACTIVE_DURING).

    Closes the gap behind #965: without this stage the deployed graph has no
    HistoricalEvent nodes and the Timeline / Narrator Activity panel renders
    empty.
    """
    _check_neo4j()

    from src.enrich.historical import run_historical_overlay
    from src.utils.neo4j_client import Neo4jClient

    print("Running historical overlay (HistoricalEvent load + ACTIVE_DURING)...")
    with Neo4jClient() as client:
        result = run_historical_overlay(client)

    print("=== historical overlay complete ===")
    print(f"  events linked          : {result.events_linked}")
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


def main() -> None:
    """Run the isnad-graph CLI."""
    parser = argparse.ArgumentParser(description="isnad-graph: Hadith Analysis Platform")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("info", help="Show configuration and database status")
    subparsers.add_parser(
        "enrich-historical",
        help="Load HistoricalEvent nodes and link narrators (ACTIVE_DURING)",
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

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "info":
        _cmd_info()
    elif args.command == "enrich-historical":
        _cmd_enrich_historical()
    elif args.command == "embed-hadiths":
        _cmd_embed_hadiths(args.batch_size, args.limit)


if __name__ == "__main__":
    main()
