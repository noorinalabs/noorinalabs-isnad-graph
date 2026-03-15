"""Tests for src.graph.load_edges — Neo4j edge loading with mock client."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.graph.load_edges import EdgeLoadResult, _build_chain_pairs, load_all_edges
from tests.test_graph.conftest import (
    MockNeo4jClient,
    write_hadiths,
    write_narrator_mentions_resolved,
    write_parallel_links,
)


class TestEdgeLoadResult:
    def test_frozen(self) -> None:
        r = EdgeLoadResult("NARRATED", 5, 1, 0)
        with pytest.raises(AttributeError):
            r.edge_type = "other"  # type: ignore[misc]


class TestBuildChainPairs:
    def test_three_narrators_two_pairs(self) -> None:
        mentions = [
            {"canonical_narrator_id": "nar:1", "position_in_chain": 0, "hadith_id": "h1"},
            {"canonical_narrator_id": "nar:2", "position_in_chain": 1, "hadith_id": "h1"},
            {"canonical_narrator_id": "nar:3", "position_in_chain": 2, "hadith_id": "h1"},
        ]
        pairs = _build_chain_pairs(mentions)
        assert len(pairs) == 2
        assert pairs[0] == {"from_id": "nar:1", "to_id": "nar:2", "position": 0, "hadith_id": "h1"}
        assert pairs[1] == {"from_id": "nar:2", "to_id": "nar:3", "position": 1, "hadith_id": "h1"}

    def test_single_narrator_no_pairs(self) -> None:
        mentions = [
            {"canonical_narrator_id": "nar:1", "position_in_chain": 0, "hadith_id": "h1"},
        ]
        assert _build_chain_pairs(mentions) == []

    def test_empty_list(self) -> None:
        assert _build_chain_pairs([]) == []

    def test_unresolved_narrators_filtered(self) -> None:
        mentions = [
            {"canonical_narrator_id": "nar:1", "position_in_chain": 0, "hadith_id": "h1"},
            {"canonical_narrator_id": None, "position_in_chain": 1, "hadith_id": "h1"},
            {"canonical_narrator_id": "nar:3", "position_in_chain": 2, "hadith_id": "h1"},
        ]
        pairs = _build_chain_pairs(mentions)
        assert len(pairs) == 1
        assert pairs[0]["from_id"] == "nar:1"
        assert pairs[0]["to_id"] == "nar:3"

    def test_sorts_by_position(self) -> None:
        mentions = [
            {"canonical_narrator_id": "nar:3", "position_in_chain": 2, "hadith_id": "h1"},
            {"canonical_narrator_id": "nar:1", "position_in_chain": 0, "hadith_id": "h1"},
            {"canonical_narrator_id": "nar:2", "position_in_chain": 1, "hadith_id": "h1"},
        ]
        pairs = _build_chain_pairs(mentions)
        assert pairs[0]["from_id"] == "nar:1"
        assert pairs[0]["to_id"] == "nar:2"
        assert pairs[1]["from_id"] == "nar:2"
        assert pairs[1]["to_id"] == "nar:3"


class TestLoadTransmittedTo:
    def test_creates_edges_from_resolved_mentions(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        # Mock all endpoint checks as existing
        mock_client.set_read_results(
            [
                {"from_id": "nar:1", "to_id": "nar:2", "from_exists": True, "to_exists": True},
            ]
        )
        write_narrator_mentions_resolved(
            staging_dir,
            [
                {
                    "mention_id": "m1",
                    "hadith_id": "h1",
                    "position_in_chain": 0,
                    "canonical_narrator_id": "nar:1",
                },
                {
                    "mention_id": "m2",
                    "hadith_id": "h1",
                    "position_in_chain": 1,
                    "canonical_narrator_id": "nar:2",
                },
            ],
        )
        results = load_all_edges(mock_client, staging_dir, curated_dir, strict=False)
        tt_result = results[0]
        assert tt_result.edge_type == "TRANSMITTED_TO"
        assert tt_result.created == 1

    def test_missing_endpoints_counted(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        mock_client.set_read_results(
            [
                {"from_id": "nar:1", "to_id": "nar:2", "from_exists": True, "to_exists": False},
            ]
        )
        write_narrator_mentions_resolved(
            staging_dir,
            [
                {
                    "mention_id": "m1",
                    "hadith_id": "h1",
                    "position_in_chain": 0,
                    "canonical_narrator_id": "nar:1",
                },
                {
                    "mention_id": "m2",
                    "hadith_id": "h1",
                    "position_in_chain": 1,
                    "canonical_narrator_id": "nar:2",
                },
            ],
        )
        results = load_all_edges(mock_client, staging_dir, curated_dir, strict=False)
        tt_result = results[0]
        assert tt_result.missing_endpoints == 1


class TestLoadNarrated:
    def test_first_narrator_per_hadith(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        # Position 0 should be chosen as the "first narrator"
        mock_client.set_read_results(
            [
                {
                    "narrator_id": "nar:1",
                    "hadith_id": "hdt:h1",
                    "narrator_exists": True,
                    "hadith_exists": True,
                },
            ]
        )
        write_narrator_mentions_resolved(
            staging_dir,
            [
                {
                    "mention_id": "m1",
                    "hadith_id": "h1",
                    "position_in_chain": 0,
                    "canonical_narrator_id": "nar:1",
                },
                {
                    "mention_id": "m2",
                    "hadith_id": "h1",
                    "position_in_chain": 1,
                    "canonical_narrator_id": "nar:2",
                },
            ],
        )
        results = load_all_edges(mock_client, staging_dir, curated_dir, strict=False)
        narrated_result = results[1]
        assert narrated_result.edge_type == "NARRATED"
        assert narrated_result.created == 1


class TestLoadAppearsIn:
    def test_hadith_to_collection_edges(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        mock_client.set_read_results(
            [
                {
                    "hadith_id": "hdt:h-1",
                    "collection_id": "col:bukhari",
                    "hadith_exists": True,
                    "collection_exists": True,
                },
            ]
        )
        write_hadiths(
            staging_dir,
            [
                {
                    "source_id": "h-1",
                    "collection_name": "bukhari",
                    "book_number": 1,
                    "chapter_number": 1,
                    "hadith_number": 1,
                },
            ],
        )
        results = load_all_edges(mock_client, staging_dir, curated_dir, strict=False)
        ai_result = results[2]
        assert ai_result.edge_type == "APPEARS_IN"
        assert ai_result.created == 1

    def test_missing_collection_name_skipped(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        write_hadiths(
            staging_dir,
            [
                {"source_id": "h-1", "collection_name": ""},  # empty
            ],
        )
        results = load_all_edges(mock_client, staging_dir, curated_dir, strict=False)
        ai_result = results[2]
        assert ai_result.skipped >= 1


class TestLoadParallelOf:
    def test_direction_enforcement(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        # id_b < id_a alphabetically, should be swapped
        mock_client.set_read_results(
            [
                {"id_a": "hdt:aaa", "id_b": "hdt:zzz", "a_exists": True, "b_exists": True},
            ]
        )
        write_parallel_links(
            staging_dir,
            [
                {"hadith_id_a": "zzz", "hadith_id_b": "aaa", "similarity_score": 0.95},
            ],
        )
        results = load_all_edges(mock_client, staging_dir, curated_dir, strict=False)
        po_result = results[3]
        assert po_result.edge_type == "PARALLEL_OF"
        # Check that the batch was direction-corrected
        write_calls = [
            (q, b) for q, b in mock_client.calls if isinstance(b, list) and b and "id_a" in b[0]
        ]
        if write_calls:
            batch = write_calls[-1][1]
            assert batch[0]["id_a"] < batch[0]["id_b"]

    def test_graceful_skip_missing_file(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        results = load_all_edges(mock_client, staging_dir, curated_dir, strict=False)
        po_result = results[3]
        assert po_result.created == 0
        assert po_result.missing_endpoints == 0

    def test_strict_raises_on_missing(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        # Need to also provide narrator_mentions and hadiths for earlier edge types
        write_narrator_mentions_resolved(
            staging_dir,
            [
                {
                    "mention_id": "m1",
                    "hadith_id": "h1",
                    "position_in_chain": 0,
                    "canonical_narrator_id": "nar:1",
                },
            ],
        )
        write_hadiths(staging_dir, [{"source_id": "h-1"}])
        # Set read results for TRANSMITTED_TO and NARRATED checks
        mock_client.set_read_results([])
        with pytest.raises(FileNotFoundError, match="parallel_links"):
            load_all_edges(mock_client, staging_dir, curated_dir, strict=True)


class TestLoadStudiedUnder:
    def test_graceful_skip_when_missing(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        results = load_all_edges(mock_client, staging_dir, curated_dir, strict=False)
        su_result = results[4]
        assert su_result.edge_type == "STUDIED_UNDER"
        assert su_result.created == 0


class TestLoadAllEdges:
    def test_returns_six_results(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        results = load_all_edges(mock_client, staging_dir, curated_dir, strict=False)
        assert len(results) == 6
        expected_types = [
            "TRANSMITTED_TO",
            "NARRATED",
            "APPEARS_IN",
            "PARALLEL_OF",
            "STUDIED_UNDER",
            "GRADED_BY",
        ]
        assert [r.edge_type for r in results] == expected_types

    def test_edge_load_result_counting(
        self, mock_client: MockNeo4jClient, staging_dir: Path, curated_dir: Path
    ) -> None:
        results = load_all_edges(mock_client, staging_dir, curated_dir, strict=False)
        for r in results:
            assert isinstance(r, EdgeLoadResult)
            assert r.created >= 0
            assert r.skipped >= 0
            assert r.missing_endpoints >= 0
