"""Phase 3: Neo4j node/edge loaders and validation queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.graph.load_edges import EdgeLoadResult, load_all_edges
from src.graph.load_nodes import LoadResult, load_all_nodes
from src.graph.validate import ValidationResult, run_validation
from src.utils.logging import get_logger
from src.utils.neo4j_client import Neo4jClient

logger = get_logger(__name__)

__all__ = [
    "EdgeLoadResult",
    "LoadResult",
    "LoadSummary",
    "ValidationResult",
    "load_all",
    "load_all_edges",
    "load_all_nodes",
    "run_validation",
]


@dataclass(frozen=True)
class LoadSummary:
    """Full pipeline outcome: nodes + edges + validation."""

    node_results: list[LoadResult]
    edge_results: list[EdgeLoadResult]
    validation_results: list[ValidationResult] = field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0
    validation_passed: bool = True


def load_all(
    client: Neo4jClient,
    staging_dir: Path,
    curated_dir: Path,
    queries_dir: Path,
    *,
    strict: bool = True,
    skip_validation: bool = False,
    nodes_only: bool = False,
) -> LoadSummary:
    """Full graph loading pipeline: nodes -> edges -> validate.

    Parameters
    ----------
    client:
        Connected Neo4j client.
    staging_dir:
        Directory containing staging Parquet files.
    curated_dir:
        Directory containing curated reference data (YAML).
    queries_dir:
        Root queries directory (contains ``validation/`` subdirectory).
    strict:
        If ``True``, raise on missing required data files.
    skip_validation:
        If ``True``, skip validation queries after loading.
    nodes_only:
        If ``True``, load only nodes (skip edges and validation).
    """
    logger.info(
        "load_all_start", strict=strict, skip_validation=skip_validation, nodes_only=nodes_only
    )

    # 1. Load nodes
    node_results = load_all_nodes(client, staging_dir, curated_dir, strict=strict)
    total_nodes = sum(r.created + r.merged for r in node_results)
    logger.info("load_all_nodes_done", total_nodes=total_nodes)

    # 2. Load edges (unless nodes_only)
    edge_results: list[EdgeLoadResult] = []
    total_edges = 0
    if not nodes_only:
        edge_results = load_all_edges(client, staging_dir, curated_dir, strict=strict)
        total_edges = sum(r.created for r in edge_results)
        logger.info("load_all_edges_done", total_edges=total_edges)

    # 3. Validate (unless skipped or nodes_only)
    validation_results: list[ValidationResult] = []
    validation_passed = True
    if not skip_validation and not nodes_only:
        validation_results = run_validation(client, queries_dir)
        validation_passed = all(v.passed for v in validation_results)
        status = "PASS" if validation_passed else "FAIL"
        logger.info("load_all_validation_done", status=status, checks=len(validation_results))

    summary = LoadSummary(
        node_results=node_results,
        edge_results=edge_results,
        validation_results=validation_results,
        total_nodes=total_nodes,
        total_edges=total_edges,
        validation_passed=validation_passed,
    )
    logger.info(
        "load_all_complete",
        total_nodes=total_nodes,
        total_edges=total_edges,
        validation_passed=validation_passed,
    )
    return summary
