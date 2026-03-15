"""Tests for src.graph.load_nodes — Neo4j node loading with mock client."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.graph.load_nodes import LoadResult, load_all_nodes
from tests.test_graph.conftest import (
    MockNeo4jClient,
    write_collections,
    write_hadiths,
    write_historical_events_yaml,
    write_locations_yaml,
    write_narrator_mentions,
    write_narrators_canonical,
)


class TestLoadResult:
    def test_frozen(self) -> None:
        r = LoadResult("Narrator", 5, 2, 1, ["err"])
        with pytest.raises(AttributeError):
            r.node_type = "other"  # type: ignore[misc]

    def test_default_errors_empty(self) -> None:
        r = LoadResult("Hadith", 0, 0, 0)
        assert r.validation_errors == []


class TestLoadNarrators:
    def test_valid_narrators(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_narrators_canonical(
            staging_dir,
            [
                {
                    "canonical_id": "nar:abu-hurayra",
                    "name_ar": "أبو هريرة",
                    "name_en": "Abu Hurayra",
                },
                {"canonical_id": "nar:anas", "name_ar": "أنس", "name_en": "Anas"},
            ],
        )
        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        narrator_result = results[0]
        assert narrator_result.node_type == "Narrator"
        assert narrator_result.created + narrator_result.merged == 2
        assert narrator_result.skipped == 0

    def test_invalid_canonical_id_skipped(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_narrators_canonical(
            staging_dir,
            [
                {"canonical_id": "nar:valid", "name_en": "Valid"},
                {"canonical_id": "INVALID", "name_en": "Bad"},  # no nar: prefix
                {"canonical_id": "", "name_en": "Empty"},
            ],
        )
        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        narrator_result = results[0]
        assert narrator_result.skipped == 2
        assert len(narrator_result.validation_errors) == 2

    def test_strict_missing_file_raises(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        with pytest.raises(FileNotFoundError, match="Missing required file"):
            load_all_nodes(mock_client, staging_dir, curated_dir, strict=True)

    def test_lenient_missing_file_returns_zeros(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        narrator_result = results[0]
        assert narrator_result.created == 0
        assert narrator_result.merged == 0


class TestLoadHadiths:
    def test_valid_hadiths(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_hadiths(
            staging_dir,
            [
                {"source_id": "h-1", "matn_ar": "text1"},
                {"source_id": "h-2", "matn_ar": "text2"},
            ],
        )
        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        hadith_result = results[1]
        assert hadith_result.node_type == "Hadith"
        assert hadith_result.created + hadith_result.merged == 2

    def test_adds_hdt_prefix(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_hadiths(staging_dir, [{"source_id": "bukhari-1"}])
        load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        # Find the hadith write batch call
        hadith_batches = [
            batch
            for query, batch in mock_client.calls
            if isinstance(batch, list)
            and batch
            and "id" in batch[0]
            and batch[0]["id"].startswith("hdt:")
        ]
        assert len(hadith_batches) >= 1
        assert hadith_batches[0][0]["id"] == "hdt:bukhari-1"

    def test_invalid_source_id_skipped(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_hadiths(
            staging_dir,
            [
                {"source_id": "h-1"},
                {"source_id": ""},  # empty
            ],
        )
        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        hadith_result = results[1]
        assert hadith_result.skipped == 1

    def test_strict_missing_hadiths_raises(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        # Provide narrators but no hadiths
        write_narrators_canonical(
            staging_dir,
            [
                {"canonical_id": "nar:test", "name_en": "Test"},
            ],
        )
        with pytest.raises(FileNotFoundError, match="hadiths_"):
            load_all_nodes(mock_client, staging_dir, curated_dir, strict=True)


class TestLoadCollections:
    def test_valid_collections(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_collections(
            staging_dir,
            [
                {"collection_id": "bukhari", "name_en": "Sahih al-Bukhari"},
                {"collection_id": "col:muslim", "name_en": "Sahih Muslim"},
            ],
        )
        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        coll_result = results[2]
        assert coll_result.node_type == "Collection"
        assert coll_result.created + coll_result.merged == 2

    def test_adds_col_prefix(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_collections(staging_dir, [{"collection_id": "bukhari", "name_en": "Bukhari"}])
        load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        coll_batches = [
            batch
            for query, batch in mock_client.calls
            if isinstance(batch, list)
            and batch
            and "id" in batch[0]
            and batch[0].get("id", "").startswith("col:")
        ]
        assert len(coll_batches) >= 1
        assert coll_batches[0][0]["id"] == "col:bukhari"


class TestLoadChains:
    def test_chains_from_mentions(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_narrator_mentions(
            staging_dir,
            [
                {
                    "mention_id": "m1",
                    "source_hadith_id": "h-1",
                    "position_in_chain": 0,
                    "name_ar": "n1",
                },
                {
                    "mention_id": "m2",
                    "source_hadith_id": "h-1",
                    "position_in_chain": 1,
                    "name_ar": "n2",
                },
                {
                    "mention_id": "m3",
                    "source_hadith_id": "h-2",
                    "position_in_chain": 0,
                    "name_ar": "n3",
                },
            ],
        )
        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        chain_result = results[3]
        assert chain_result.node_type == "Chain"
        assert chain_result.created + chain_result.merged == 2  # 2 distinct hadiths


class TestLoadGradings:
    def test_gradings_from_hadiths(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_hadiths(
            staging_dir,
            [
                {"source_id": "h-1", "grade": "sahih"},
                {"source_id": "h-2", "grade": "hasan"},
                {"source_id": "h-3"},  # no grade
            ],
        )
        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        grading_result = results[4]
        assert grading_result.node_type == "Grading"
        assert grading_result.created + grading_result.merged == 2


class TestLoadHistoricalEvents:
    def test_valid_events(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_historical_events_yaml(
            curated_dir,
            [
                {"id": "evt:ridda", "name_en": "Ridda Wars", "year_start_ah": 11},
                {"id": "evt:badr", "name_en": "Battle of Badr", "year_start_ah": 2},
            ],
        )
        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        event_result = results[5]
        assert event_result.node_type == "HistoricalEvent"
        assert event_result.created + event_result.merged == 2

    def test_missing_name_skipped(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_historical_events_yaml(
            curated_dir,
            [
                {"id": "evt:1", "name_en": "Valid"},
                {"id": "evt:2"},  # missing name_en
            ],
        )
        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        event_result = results[5]
        assert event_result.skipped == 1

    def test_invalid_id_skipped(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_historical_events_yaml(
            curated_dir,
            [
                {"id": "", "name_en": "Bad ID"},
            ],
        )
        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        event_result = results[5]
        assert event_result.skipped == 1


class TestLoadLocations:
    def test_valid_locations(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_locations_yaml(
            curated_dir,
            [
                {"id": "loc:medina", "name_en": "Medina", "region": "Hejaz"},
                {"id": "mecca", "name_en": "Mecca"},
            ],
        )
        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        loc_result = results[6]
        assert loc_result.node_type == "Location"
        assert loc_result.created + loc_result.merged == 2

    def test_missing_file_returns_zeros(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        # Locations are optional even in strict mode
        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        loc_result = results[6]
        assert loc_result.created == 0


class TestLoadAllNodes:
    def test_ensures_constraints_first(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        assert mock_client.constraints_ensured

    def test_returns_seven_results(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        assert len(results) == 7
        expected_types = [
            "Narrator",
            "Hadith",
            "Collection",
            "Chain",
            "Grading",
            "HistoricalEvent",
            "Location",
        ]
        assert [r.node_type for r in results] == expected_types

    def test_full_load_with_all_data(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_narrators_canonical(
            staging_dir,
            [
                {"canonical_id": "nar:1", "name_en": "Narrator 1"},
            ],
        )
        write_hadiths(
            staging_dir,
            [
                {"source_id": "h-1", "grade": "sahih", "collection_name": "bukhari"},
            ],
        )
        write_collections(
            staging_dir,
            [
                {"collection_id": "bukhari", "name_en": "Bukhari"},
            ],
        )
        write_narrator_mentions(
            staging_dir,
            [
                {
                    "mention_id": "m1",
                    "source_hadith_id": "h-1",
                    "position_in_chain": 0,
                    "name_ar": "n",
                },
            ],
        )
        write_historical_events_yaml(
            curated_dir,
            [
                {"id": "evt:1", "name_en": "Event"},
            ],
        )
        write_locations_yaml(
            curated_dir,
            [
                {"id": "loc:1", "name_en": "Place"},
            ],
        )

        results = load_all_nodes(mock_client, staging_dir, curated_dir, strict=False)
        assert all(r.created + r.merged > 0 or r.node_type in ("Chain",) for r in results)
