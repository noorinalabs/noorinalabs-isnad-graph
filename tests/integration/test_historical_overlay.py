"""Integration test for the historical overlay against a real Neo4j container.

Proves the #965 fix end-to-end: running the overlay loads HistoricalEvent nodes
with the property names the /timeline API reads and creates ACTIVE_DURING edges
for narrators whose lifespan overlaps an event. Gated by ``pytest.mark.integration``
(run via ``make test-integration`` — requires Docker).
"""

from __future__ import annotations

import pytest

from src.enrich.historical import load_events_from_yaml, run_historical_overlay
from src.models.enums import DatePrecision
from src.models.narrator import NarratorDates
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


@pytest.fixture
def _seed_bounds_narrator(neo4j_client: Neo4jClient) -> None:
    """Seed a death-only narrator whose point estimate misses the Mihna."""
    neo4j_client.ensure_constraints()
    neo4j_client.execute_write_batch(
        """
        UNWIND $batch AS row
        MERGE (n:Narrator {id: row.id})
        SET n.name_en = row.name_en,
            n.birth_year_ah = row.birth_year_ah,
            n.death_year_ah = row.death_year_ah
        """,
        # Point death 200, no birth → estimate window [120, 200]; the Mihna
        # (218-234) is OUT of range until a resolved death_latest widens it.
        [
            {
                "id": "nar:bounds",
                "name_en": "Bounds Test",
                "birth_year_ah": None,
                "death_year_ah": 200,
            }
        ],
    )


def test_resolved_dates_loaded_then_widen_window_to_link_mihna(
    neo4j_client: Neo4jClient, _seed_bounds_narrator: None
) -> None:
    """ig#1039: the loader writes resolved bounds; the link uses the real window.

    This is the schema-shaped end-to-end leg — it drives :class:`NarratorDates`
    fixtures matching the agreed da#161-166 contract, NOT real reconciled data
    (that e2e is gated below until the da chain lands).
    """
    # Baseline: without resolved bounds the point estimate window [120, 200] does
    # not reach the Mihna (218-234).
    run_historical_overlay(neo4j_client)
    before = neo4j_client.execute_read(
        """
        MATCH (n:Narrator {id: 'nar:bounds'})-[:ACTIVE_DURING]->(e:HistoricalEvent)
        WHERE e.id = 'evt:mihna'
        RETURN count(e) AS n
        """
    )
    assert before[0]["n"] == 0

    # Load resolved dates: death_latest=240 widens the window to [160, 240], which
    # overlaps the Mihna.
    records = [
        NarratorDates(
            id="nar:bounds",
            death_year_ah=200,
            death_year_ah_latest=240,
            death_date_precision=DatePrecision.AFTER,
        )
    ]
    result = run_historical_overlay(neo4j_client, narrator_dates=records)
    assert result.narrators_dated == 1

    # The resolved props landed on the node.
    props = neo4j_client.execute_read(
        """
        MATCH (n:Narrator {id: 'nar:bounds'})
        RETURN n.death_year_ah_latest AS latest, n.death_date_precision AS precision
        """
    )
    assert props[0]["latest"] == 240
    assert props[0]["precision"] == "after"

    # And the widened window now links the narrator to the Mihna.
    after = neo4j_client.execute_read(
        """
        MATCH (n:Narrator {id: 'nar:bounds'})-[:ACTIVE_DURING]->(e:HistoricalEvent)
        WHERE e.id = 'evt:mihna'
        RETURN count(e) AS n
        """
    )
    assert after[0]["n"] == 1


@pytest.mark.skip(
    reason="Real-reconciled-dates e2e depends on the da#161-166 date chain landing "
    "(DatePrecision model/schema/parse/reconcile/fallback). Until then this leg is "
    "covered by the schema-shaped NarratorDates fixture test above. See ig#1039."
)
def test_real_reconciled_dates_end_to_end(neo4j_client: Neo4jClient) -> None:  # pragma: no cover
    """Placeholder: load the actual reconciled narrators_canonical date columns.

    Unskip once the data-acquisition reconcile output (da#161-166) is available
    and exported to the resolved-date JSON the loader consumes.
    """
    raise NotImplementedError
