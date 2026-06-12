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


def main() -> None:
    """Run the isnad-graph CLI."""
    parser = argparse.ArgumentParser(description="isnad-graph: Hadith Analysis Platform")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("info", help="Show configuration and database status")
    subparsers.add_parser(
        "enrich-historical",
        help="Load HistoricalEvent nodes and link narrators (ACTIVE_DURING)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "info":
        _cmd_info()
    elif args.command == "enrich-historical":
        _cmd_enrich_historical()


if __name__ == "__main__":
    main()
