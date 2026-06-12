"""Integration test for the historical overlay against a real Neo4j container.

Proves the #965 fix end-to-end: running the overlay loads HistoricalEvent nodes
with the property names the /timeline API reads and creates ACTIVE_DURING edges
for narrators whose lifespan overlaps an event. Gated by ``pytest.mark.integration``
(run via ``make test-integration`` — requires Docker).
"""

from __future__ import annotations

import pytest

from src.enrich.historical import load_events_from_yaml, run_historical_overlay
from src.utils.neo4j_client import Neo4jClient

pytestmark = pytest.mark.integration


@pytest.fixture
def _seed_narrators(neo4j_client: Neo4jClient) -> None:
    """Seed narrators spanning a range of date-completeness cases."""
    neo4j_client.ensure_constraints()
    neo4j_client.execute_write_batch(
        """
        UNWIND $batch AS row
        MERGE (n:Narrator {id: row.id})
        SET n.name_en = row.name_en,
            n.birth_year_ah = row.birth_year_ah,
            n.death_year_ah = row.death_year_ah
        """,
        [
            # Full lifespan overlapping the Rashidun/Umayyad era.
            {
                "id": "nar:abu-hurayra",
                "name_en": "Abu Hurayra",
                "birth_year_ah": -21,
                "death_year_ah": 59,
            },
            # Death-only (the common hadith-bio case) — Abbasid era.
            {
                "id": "nar:bukhari",
                "name_en": "al-Bukhari",
                "birth_year_ah": None,
                "death_year_ah": 256,
            },
            # No dates at all — must be skipped, never linked.
            {
                "id": "nar:unknown",
                "name_en": "Unknown",
                "birth_year_ah": None,
                "death_year_ah": None,
            },
        ],
    )


def test_historical_overlay_loads_events_and_links_narrators(
    neo4j_client: Neo4jClient, _seed_narrators: None
) -> None:
    result = run_historical_overlay(neo4j_client)

    curated = load_events_from_yaml()

    # Every curated event lands as a node.
    event_count = neo4j_client.execute_read("MATCH (e:HistoricalEvent) RETURN count(e) AS n")
    assert event_count[0]["n"] == len(curated)

    # Nodes carry the property names src/api/routes/timeline.py reads.
    sample = neo4j_client.execute_read(
        """
        MATCH (e:HistoricalEvent {id: 'evt:mihna'})
        RETURN e.name AS name, e.year_ah AS year_ah,
               e.end_year_ah AS end_year_ah, e.event_type AS event_type
        """
    )
    assert sample[0]["name"] == "Mihna (Inquisition)"
    assert sample[0]["year_ah"] == 218
    assert sample[0]["event_type"] == "theological_controversy"

    # ACTIVE_DURING edges were created and the no-date narrator was skipped.
    edges = neo4j_client.execute_read(
        "MATCH (:Narrator)-[r:ACTIVE_DURING]->(:HistoricalEvent) RETURN count(r) AS n"
    )
    assert edges[0]["n"] == result.edges_created > 0
    assert result.narrators_skipped_no_dates == 1
    assert result.narrators_linked == 2  # abu-hurayra + bukhari, not unknown

    # al-Bukhari (d. 256 AH, death-only) links to the Mihna (218-234 AH).
    bukhari_links = neo4j_client.execute_read(
        """
        MATCH (n:Narrator {id: 'nar:bukhari'})-[:ACTIVE_DURING]->(e:HistoricalEvent)
        RETURN e.id AS id
        """
    )
    assert "evt:mihna" in {row["id"] for row in bukhari_links}


def test_historical_overlay_is_idempotent(neo4j_client: Neo4jClient, _seed_narrators: None) -> None:
    """Re-running reconciles rather than duplicating nodes or edges."""
    first = run_historical_overlay(neo4j_client)
    run_historical_overlay(neo4j_client)

    curated = load_events_from_yaml()
    event_count = neo4j_client.execute_read("MATCH (e:HistoricalEvent) RETURN count(e) AS n")
    edge_count = neo4j_client.execute_read(
        "MATCH (:Narrator)-[r:ACTIVE_DURING]->(:HistoricalEvent) RETURN count(r) AS n"
    )
    assert event_count[0]["n"] == len(curated)
    # Same edge set after a second run — no duplicates.
    assert edge_count[0]["n"] == first.edges_created
