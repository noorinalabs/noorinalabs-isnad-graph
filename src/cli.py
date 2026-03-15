"""CLI entry point for the isnad-graph platform."""

from __future__ import annotations

import argparse
import sys


def _mask_password(value: str) -> str:
    """Replace all but first and last character with asterisks."""
    if len(value) <= 2:
        return "*" * len(value)
    return value[0] + "*" * (len(value) - 2) + value[-1]


def _cmd_info() -> None:
    """Print configuration (masked passwords) and check DB connectivity."""
    from src.config import get_settings

    settings = get_settings()

    print("=== isnad-graph configuration ===")
    print(f"  neo4j.uri      : {settings.neo4j.uri}")
    print(f"  neo4j.user     : {settings.neo4j.user}")
    print(f"  neo4j.password : {_mask_password(settings.neo4j.password)}")
    print(f"  postgres.dsn   : {settings.postgres.dsn}")
    print(f"  redis.url      : {settings.redis.url}")
    print(f"  data_raw_dir   : {settings.data_raw_dir}")
    print(f"  data_staging_dir: {settings.data_staging_dir}")
    print(f"  data_curated_dir: {settings.data_curated_dir}")
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

        conn = psycopg.connect(settings.postgres.dsn)
        conn.close()
        print("  postgres : connected")
    except Exception:  # noqa: BLE001
        print("  postgres : unavailable")


def _cmd_acquire() -> None:
    """Run all data acquisition downloaders."""
    from pathlib import Path

    from src.acquire import run_all as acquire_all
    from src.config import get_settings

    settings = get_settings()
    results = acquire_all(Path(settings.data_raw_dir))
    ok = sum(1 for v in results.values() if v)
    print(f"Acquisition complete. {ok}/{len(results)} sources downloaded.")


def _cmd_parse() -> None:
    """Run all parsers to produce staging Parquet files."""
    from pathlib import Path

    from src.config import get_settings
    from src.parse import run_all as parse_all

    settings = get_settings()
    results = parse_all(Path(settings.data_raw_dir), Path(settings.data_staging_dir))
    total_files = sum(len(v) for v in results.values())
    print(f"Parsing complete. {total_files} staging files produced.")


def _cmd_resolve() -> None:
    """Run the Phase 2 entity resolution pipeline."""
    from pathlib import Path

    from src.config import get_settings
    from src.resolve import run_all as resolve_all

    settings = get_settings()
    results = resolve_all(
        Path(settings.data_raw_dir),
        Path(settings.data_staging_dir),
        Path(settings.data_curated_dir),
    )
    total = sum(len(v) for v in results.values())
    print(f"\nResolution complete. {total} output files.")


def _cmd_load(*, skip_validation: bool = False, nodes_only: bool = False) -> None:
    """Run the Phase 3 graph loading pipeline."""
    from pathlib import Path

    from neo4j import GraphDatabase

    from src.config import get_settings

    settings = get_settings()

    # Pre-flight Neo4j connectivity check
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

    from src.graph import load_all
    from src.utils.neo4j_client import Neo4jClient

    staging_dir = Path(settings.data_staging_dir)
    curated_dir = Path(settings.data_curated_dir)
    queries_dir = Path("queries")

    with Neo4jClient() as client:
        summary = load_all(
            client,
            staging_dir,
            curated_dir,
            queries_dir,
            strict=False,
            skip_validation=skip_validation,
            nodes_only=nodes_only,
        )

    print("\n=== Load Summary ===")
    print(f"  Nodes loaded : {summary.total_nodes}")
    print(f"  Edges loaded : {summary.total_edges}")

    for nr in summary.node_results:
        print(f"    {nr.node_type}: created={nr.created} merged={nr.merged} skipped={nr.skipped}")
    for er in summary.edge_results:
        print(
            f"    {er.edge_type}: created={er.created} skipped={er.skipped}"
            f" missing_endpoints={er.missing_endpoints}"
        )

    if summary.validation_results:
        print("\n=== Validation ===")
        for vr in summary.validation_results:
            status = "PASS" if vr.passed else "FAIL"
            print(f"  [{status}] {vr.query_name}: {vr.details}")
        if not summary.validation_passed:
            print("\nWARNING: Some validation checks failed.")
            sys.exit(1)
        else:
            print("\nAll validation checks passed.")


def _cmd_validate() -> None:
    """Run graph validation queries against an existing Neo4j database."""
    from pathlib import Path

    from neo4j import GraphDatabase

    from src.config import get_settings

    settings = get_settings()

    # Pre-flight connectivity check
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

    from src.graph.validate import run_validation
    from src.utils.neo4j_client import Neo4jClient

    queries_dir = Path("queries")

    with Neo4jClient() as client:
        results = run_validation(client, queries_dir)

    if not results:
        print("No validation queries found.")
        sys.exit(0)

    print("=== Validation Results ===")
    all_passed = True
    for vr in results:
        status = "PASS" if vr.passed else "FAIL"
        print(f"  [{status}] {vr.query_name}: {vr.details}")
        if not vr.passed:
            all_passed = False

    if not all_passed:
        print("\nWARNING: Some validation checks failed.")
        sys.exit(1)
    else:
        print("\nAll validation checks passed.")


def _cmd_stub(name: str) -> None:
    """Print a not-yet-implemented message for a pipeline stage."""
    print(f"Command '{name}' not yet implemented. See Makefile targets.")


def main() -> None:
    """Run the isnad-graph CLI."""
    parser = argparse.ArgumentParser(description="isnad-graph: Hadith Analysis Platform")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("info", help="Show configuration and database status")
    subparsers.add_parser("acquire", help="Download data sources")
    subparsers.add_parser("parse", help="Parse raw data to staging")
    subparsers.add_parser("resolve", help="Entity resolution")
    load_parser = subparsers.add_parser("load", help="Load graph database")
    load_parser.add_argument(
        "--skip-validation", action="store_true", help="Skip validation queries after loading"
    )
    load_parser.add_argument(
        "--nodes-only", action="store_true", help="Load only nodes (skip edges and validation)"
    )
    subparsers.add_parser("enrich", help="Compute metrics and enrichment")
    subparsers.add_parser("validate", help="Run graph validation queries")
    subparsers.add_parser("validate-staging", help="Validate staging Parquet files")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "info":
        _cmd_info()
    elif args.command == "acquire":
        _cmd_acquire()
    elif args.command == "parse":
        _cmd_parse()
    elif args.command == "validate-staging":
        from pathlib import Path

        from src.config import get_settings
        from src.parse.validate import validate_staging

        settings = get_settings()
        validate_staging(Path(settings.data_staging_dir))
    elif args.command == "resolve":
        _cmd_resolve()
    elif args.command == "load":
        _cmd_load(
            skip_validation=args.skip_validation,
            nodes_only=args.nodes_only,
        )
    elif args.command == "validate":
        _cmd_validate()
    else:
        _cmd_stub(args.command)


if __name__ == "__main__":
    main()
