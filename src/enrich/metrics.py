"""Graph metrics computation using Neo4j GDS.

Computes betweenness centrality, PageRank, Louvain community detection,
and in/out degree for NARRATOR nodes via the TRANSMITTED_TO relationship.
"""

from __future__ import annotations

from neo4j import exceptions as neo4j_exc

from src.models.enrich import MetricsResult
from src.utils.logging import get_logger
from src.utils.neo4j_client import Neo4jClient

__all__ = ["run_metrics"]

log = get_logger(__name__)

GRAPH_NAME = "transmission_graph"


def _gds_available(client: Neo4jClient) -> bool:
    """Check whether the GDS library is installed."""
    try:
        client.execute_read("RETURN gds.version() AS version")
        return True
    except neo4j_exc.Neo4jError as exc:
        log.error("gds_not_available", error=str(exc))
        return False


def _ensure_graph_projection(client: Neo4jClient) -> None:
    """Create the GDS graph projection, dropping any stale one first."""
    rows = client.execute_read(
        "CALL gds.graph.exists($name) YIELD exists RETURN exists",
        {"name": GRAPH_NAME},
    )
    if rows and rows[0].get("exists"):
        client.execute_write(
            "CALL gds.graph.drop($name) YIELD graphName RETURN graphName",
            {"name": GRAPH_NAME},
        )
        log.info("gds_graph_dropped", graph=GRAPH_NAME)

    client.execute_write(
        "CALL gds.graph.project($name, 'Narrator', 'TRANSMITTED_TO')"
        " YIELD graphName, nodeCount, relationshipCount"
        " RETURN graphName, nodeCount, relationshipCount",
        {"name": GRAPH_NAME},
    )
    log.info("gds_graph_projected", graph=GRAPH_NAME)


def _drop_graph(client: Neo4jClient) -> None:
    """Drop the GDS graph projection."""
    try:
        client.execute_write(
            "CALL gds.graph.drop($name) YIELD graphName RETURN graphName",
            {"name": GRAPH_NAME},
        )
        log.info("gds_graph_dropped", graph=GRAPH_NAME)
    except neo4j_exc.Neo4jError as exc:
        log.warning("gds_graph_drop_failed", error=str(exc))


def run_metrics(client: Neo4jClient) -> MetricsResult:
    """Compute graph metrics and write back to NARRATOR nodes."""
    if not _gds_available(client):
        return MetricsResult(
            narrators_enriched=0,
            betweenness_computed=False,
            pagerank_computed=False,
            louvain_computed=False,
            degree_computed=False,
            communities_found=0,
        )

    _ensure_graph_projection(client)

    try:
        # Betweenness centrality
        client.execute_write(
            "CALL gds.betweenness.write($name, {writeProperty: 'betweenness_centrality'})"
            " YIELD nodePropertiesWritten RETURN nodePropertiesWritten",
            {"name": GRAPH_NAME},
        )
        betweenness_computed = True
        log.info("betweenness_computed")

        # PageRank
        client.execute_write(
            "CALL gds.pageRank.write($name, {writeProperty: 'pagerank'})"
            " YIELD nodePropertiesWritten RETURN nodePropertiesWritten",
            {"name": GRAPH_NAME},
        )
        pagerank_computed = True
        log.info("pagerank_computed")

        # Louvain community detection
        louvain_rows = client.execute_write(
            "CALL gds.louvain.write($name, {writeProperty: 'community_id'})"
            " YIELD communityCount, nodePropertiesWritten"
            " RETURN communityCount, nodePropertiesWritten",
            {"name": GRAPH_NAME},
        )
        louvain_computed = True
        communities_found = louvain_rows[0]["communityCount"] if louvain_rows else 0
        log.info("louvain_computed", communities=communities_found)

        # Out-degree
        client.execute_write(
            "CALL gds.degree.write($name, {writeProperty: 'out_degree'})"
            " YIELD nodePropertiesWritten RETURN nodePropertiesWritten",
            {"name": GRAPH_NAME},
        )
        log.info("out_degree_computed")

        # In-degree
        client.execute_write(
            "CALL gds.degree.write($name, {writeProperty: 'in_degree', orientation: 'REVERSE'})"
            " YIELD nodePropertiesWritten RETURN nodePropertiesWritten",
            {"name": GRAPH_NAME},
        )
        degree_computed = True
        log.info("in_degree_computed")

        # Count enriched narrators
        count_rows = client.execute_read(
            "MATCH (n:Narrator) WHERE n.betweenness_centrality IS NOT NULL RETURN count(n) AS cnt"
        )
        narrators_enriched = count_rows[0]["cnt"] if count_rows else 0

        # Sanity check: top-5 narrators by betweenness
        top5 = client.execute_read(
            "MATCH (n:Narrator)"
            " WHERE n.betweenness_centrality IS NOT NULL"
            " RETURN n.id AS id, n.name_arabic AS name, n.betweenness_centrality AS bc"
            " ORDER BY bc DESC LIMIT 5"
        )
        for row in top5:
            log.info(
                "top_narrator_betweenness",
                narrator_id=row.get("id"),
                name=row.get("name"),
                betweenness=row.get("bc"),
            )

        return MetricsResult(
            narrators_enriched=narrators_enriched,
            betweenness_computed=betweenness_computed,
            pagerank_computed=pagerank_computed,
            louvain_computed=louvain_computed,
            degree_computed=degree_computed,
            communities_found=communities_found,
        )
    finally:
        _drop_graph(client)
