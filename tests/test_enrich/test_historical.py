"""Tests for src.enrich.historical — ACTIVE_DURING edge creation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.enrich.historical import run_historical_overlay
from src.models.enrich import HistoricalResult


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.execute_read.return_value = []
    client.execute_write.return_value = []
    client.execute_write_batch.return_value = 0
    return client


def _make_narrator(nid: str, birth: int, death: int) -> dict[str, str | int]:
    return {"id": nid, "birth_year_ah": birth, "death_year_ah": death}


def _make_event(eid: str, start: int, end: int) -> dict[str, str | int]:
    return {"id": eid, "year_start_ah": start, "year_end_ah": end}


class TestDateOverlap:
    """Test the overlap logic: narrator alive during any part of event."""

    def test_narrator_alive_during_event(self, mock_client: MagicMock) -> None:
        """Narrator born=10, died=80; event 50-60 => overlap."""
        mock_client.execute_read.side_effect = [
            [_make_event("e1", 50, 60)],  # events
            [_make_narrator("n1", 10, 80)],  # narrators
            [{"cnt": 0}],  # no-dates count
        ]
        mock_client.execute_write_batch.return_value = 1

        result = run_historical_overlay(mock_client)

        assert result.edges_created == 1
        assert result.narrators_linked == 1
        assert result.events_linked == 1

        batch_arg = mock_client.execute_write_batch.call_args.args[1]
        assert {"narrator_id": "n1", "event_id": "e1"} in batch_arg

    def test_narrator_born_after_event(self, mock_client: MagicMock) -> None:
        """Narrator born=100, died=170; event 50-60 => no overlap."""
        mock_client.execute_read.side_effect = [
            [_make_event("e1", 50, 60)],
            [_make_narrator("n1", 100, 170)],
            [{"cnt": 0}],
        ]

        result = run_historical_overlay(mock_client)

        assert result.edges_created == 0
        assert result.narrators_linked == 0
        assert result.events_linked == 0
        mock_client.execute_write_batch.assert_not_called()

    def test_narrator_died_before_event(self, mock_client: MagicMock) -> None:
        """Narrator born=10, died=40; event 50-60 => no overlap."""
        mock_client.execute_read.side_effect = [
            [_make_event("e1", 50, 60)],
            [_make_narrator("n1", 10, 40)],
            [{"cnt": 0}],
        ]

        result = run_historical_overlay(mock_client)

        assert result.edges_created == 0
        assert result.narrators_linked == 0


class TestMaxLifetimeFilter:
    """Narrators with lifespan > 120 AH should be skipped."""

    def test_unrealistic_lifespan_skipped(self, mock_client: MagicMock) -> None:
        mock_client.execute_read.side_effect = [
            [_make_event("e1", 50, 60)],
            [_make_narrator("n1", 10, 200)],  # 190-year lifespan
            [{"cnt": 0}],
        ]

        result = run_historical_overlay(mock_client)

        assert result.narrators_skipped_max_lifetime == 1
        assert result.narrators_linked == 0
        mock_client.execute_write_batch.assert_not_called()

    def test_exactly_120_not_skipped(self, mock_client: MagicMock) -> None:
        """Lifespan == 120 should NOT be skipped (only > 120)."""
        mock_client.execute_read.side_effect = [
            [_make_event("e1", 50, 60)],
            [_make_narrator("n1", 0, 120)],  # exactly 120
            [{"cnt": 0}],
        ]
        mock_client.execute_write_batch.return_value = 1

        result = run_historical_overlay(mock_client)

        assert result.narrators_skipped_max_lifetime == 0
        assert result.narrators_linked == 1

    def test_121_skipped(self, mock_client: MagicMock) -> None:
        mock_client.execute_read.side_effect = [
            [_make_event("e1", 50, 60)],
            [_make_narrator("n1", 0, 121)],  # 121 > 120
            [{"cnt": 0}],
        ]

        result = run_historical_overlay(mock_client)

        assert result.narrators_skipped_max_lifetime == 1


class TestHistoricalResult:
    """Verify result model counts."""

    def test_result_counts(self, mock_client: MagicMock) -> None:
        mock_client.execute_read.side_effect = [
            [_make_event("e1", 50, 60), _make_event("e2", 70, 80)],
            [
                _make_narrator("n1", 10, 90),
                _make_narrator("n2", 60, 100),
            ],
            [{"cnt": 3}],  # 3 narrators without dates
        ]
        mock_client.execute_write_batch.return_value = 3

        result = run_historical_overlay(mock_client)

        assert isinstance(result, HistoricalResult)
        assert result.edges_created == 3
        assert result.narrators_linked == 2
        assert result.events_linked == 2
        assert result.narrators_skipped_no_dates == 3
        assert result.narrators_skipped_max_lifetime == 0


class TestEdgeBatchCall:
    """Verify execute_write_batch is called with the correct query."""

    def test_batch_query_uses_merge(self, mock_client: MagicMock) -> None:
        mock_client.execute_read.side_effect = [
            [_make_event("e1", 50, 60)],
            [_make_narrator("n1", 10, 80)],
            [{"cnt": 0}],
        ]
        mock_client.execute_write_batch.return_value = 1

        run_historical_overlay(mock_client)

        query_arg = mock_client.execute_write_batch.call_args.args[0]
        assert "MERGE" in query_arg
        assert "ACTIVE_DURING" in query_arg
