"""Tests for src.enrich.topics — zero-shot topic classification."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.enrich.topics import MIN_TEXT_LENGTH, MODEL_NAME, TOPIC_LABELS, run_topics
from src.models.enrich import TopicResult


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.execute_read.return_value = []
    client.execute_write.return_value = []
    return client


class TestTopicLabels:
    """Validate the TOPIC_LABELS constant."""

    def test_has_14_entries(self) -> None:
        assert len(TOPIC_LABELS) == 14

    def test_all_strings(self) -> None:
        assert all(isinstance(label, str) for label in TOPIC_LABELS)

    def test_no_duplicates(self) -> None:
        assert len(TOPIC_LABELS) == len(set(TOPIC_LABELS))


class TestShortTextFiltering:
    """Texts shorter than MIN_TEXT_LENGTH should be skipped."""

    def test_short_texts_skipped(self, mock_client: MagicMock) -> None:
        short_text = "x" * (MIN_TEXT_LENGTH - 1)
        mock_client.execute_read.return_value = [
            {"id": "h1", "matn_en": short_text},
            {"id": "h2", "matn_en": short_text},
        ]

        mock_classifier = MagicMock()
        with patch("src.enrich.topics._load_pipeline", return_value=mock_classifier):
            result = run_topics(mock_client)

        assert result.hadiths_skipped == 2
        assert result.hadiths_classified == 0
        mock_classifier.assert_not_called()


class TestTopicResult:
    """Verify TopicResult model is correct."""

    def test_model_fields(self) -> None:
        result = TopicResult(
            hadiths_classified=10,
            hadiths_skipped=2,
            model_name=MODEL_NAME,
            labels_used=TOPIC_LABELS,
        )
        assert result.hadiths_classified == 10
        assert result.model_name == MODEL_NAME
        assert len(result.labels_used) == 14


class TestGracefulSkip:
    """Run_topics should return zeros when transformers unavailable."""

    def test_returns_zero_result_without_transformers(
        self,
        mock_client: MagicMock,
    ) -> None:
        with patch("src.enrich.topics._load_pipeline", return_value=None):
            result = run_topics(mock_client)

        assert isinstance(result, TopicResult)
        assert result.hadiths_classified == 0
        assert result.hadiths_skipped == 0
        assert result.model_name == MODEL_NAME
        assert result.labels_used == TOPIC_LABELS


@pytest.mark.ml
class TestClassification:
    """ML-gated tests that require transformers."""

    def test_classification_with_mock_pipeline(
        self,
        mock_client: MagicMock,
    ) -> None:
        """Test full classification flow with a mocked classifier."""
        sample_text = "The Prophet performed the prayer at dawn and recited the Quran."
        mock_client.execute_read.return_value = [
            {"id": "h1", "matn_en": sample_text},
        ]

        mock_classifier = MagicMock()
        mock_classifier.return_value = {
            "labels": ["ritual/worship", "theology", "ethics/conduct"] + TOPIC_LABELS[3:],
            "scores": [0.65, 0.20, 0.10] + [0.005] * 11,
        }

        with patch("src.enrich.topics._load_pipeline", return_value=mock_classifier):
            result = run_topics(mock_client)

        assert result.hadiths_classified == 1
        assert result.hadiths_skipped == 0
        mock_classifier.assert_called_once()

        # Verify write was called with topic data
        write_call = mock_client.execute_write.call_args
        assert write_call is not None
        batch = write_call.kwargs.get("parameters") or write_call.args[1]
        row = batch["batch"][0]
        assert row["t1"] == "ritual/worship"
        assert row["s1"] == 0.65
