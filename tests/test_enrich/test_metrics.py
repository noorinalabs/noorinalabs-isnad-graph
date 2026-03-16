"""Tests for src.enrich.metrics — graph metrics via Neo4j GDS."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from neo4j import exceptions as neo4j_exc

from src.enrich.metrics import _gds_available, run_metrics
from src.models.enrich import MetricsResult


@pytest.fixture
def mock_client() -> MagicMock:
    """A mock Neo4jClient with default read/write returns."""
    client = MagicMock()
    client.execute_read.return_value = []
    client.execute_write.return_value = []
    return client


class TestGdsAvailable:
    """Tests for _gds_available helper."""

    def test_returns_true_when_gds_installed(self, mock_client: MagicMock) -> None:
        mock_client.execute_read.return_value = [{"version": "2.6.0"}]
        assert _gds_available(mock_client) is True
        mock_client.execute_read.assert_called_once_with("RETURN gds.version() AS version")

    def test_returns_false_when_gds_missing(self, mock_client: MagicMock) -> None:
        mock_client.execute_read.side_effect = neo4j_exc.Neo4jError(
            "Unknown function 'gds.version'"
        )
        assert _gds_available(mock_client) is False


class TestRunMetrics:
    """Tests for run_metrics orchestration."""

    def test_graceful_fallback_when_gds_unavailable(self, mock_client: MagicMock) -> None:
        mock_client.execute_read.side_effect = neo4j_exc.Neo4jError("gds not installed")
        result = run_metrics(mock_client)
        assert isinstance(result, MetricsResult)
        assert result.narrators_enriched == 0
        assert result.betweenness_computed is False
        assert result.pagerank_computed is False
        assert result.louvain_computed is False
        assert result.degree_computed is False
        assert result.communities_found == 0

    def test_graph_projection_call_sequence(self, mock_client: MagicMock) -> None:
        """Verify that run_metrics projects the graph, runs algos, and drops."""
        # _gds_available check
        read_responses = [
            [{"version": "2.6.0"}],  # gds.version()
            [{"exists": True}],  # gds.graph.exists
            [{"cnt": 42}],  # count enriched narrators
            [],  # top-5 query
        ]
        mock_client.execute_read.side_effect = read_responses
        mock_client.execute_write.return_value = [
            {"communityCount": 5, "nodePropertiesWritten": 10}
        ]

        result = run_metrics(mock_client)

        assert isinstance(result, MetricsResult)
        assert result.betweenness_computed is True
        assert result.pagerank_computed is True
        assert result.louvain_computed is True
        assert result.degree_computed is True
        assert result.communities_found == 5
        assert result.narrators_enriched == 42

        # Verify graph drop was called in the finally block
        write_calls = mock_client.execute_write.call_args_list
        last_write = write_calls[-1]
        assert "gds.graph.drop" in last_write.args[0]

    def test_returns_metrics_result(self, mock_client: MagicMock) -> None:
        mock_client.execute_read.side_effect = [
            [{"version": "2.6.0"}],  # gds check
            [{"exists": False}],  # graph exists
            [{"cnt": 10}],  # count
            [{"id": "n1", "name": "Test", "bc": 0.5}],  # top-5
        ]
        mock_client.execute_write.return_value = [
            {"communityCount": 3, "nodePropertiesWritten": 10}
        ]

        result = run_metrics(mock_client)
        assert isinstance(result, MetricsResult)
        data = result.model_dump()
        assert set(data.keys()) == {
            "narrators_enriched",
            "betweenness_computed",
            "pagerank_computed",
            "louvain_computed",
            "degree_computed",
            "communities_found",
        }
