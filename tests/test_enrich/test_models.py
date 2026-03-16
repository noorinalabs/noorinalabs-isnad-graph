"""Tests for src.models.enrich — enrichment result models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.enrich.topics import TOPIC_LABELS
from src.models.enrich import EnrichSummary, HistoricalResult, MetricsResult, TopicResult


class TestMetricsResult:
    def test_construction(self) -> None:
        m = MetricsResult(
            narrators_enriched=100,
            betweenness_computed=True,
            pagerank_computed=True,
            louvain_computed=True,
            degree_computed=True,
            communities_found=5,
        )
        assert m.narrators_enriched == 100
        assert m.communities_found == 5

    def test_frozen(self) -> None:
        m = MetricsResult(
            narrators_enriched=0,
            betweenness_computed=False,
            pagerank_computed=False,
            louvain_computed=False,
            degree_computed=False,
            communities_found=0,
        )
        with pytest.raises(ValidationError):
            m.narrators_enriched = 1  # type: ignore[misc]

    def test_model_dump_roundtrip(self) -> None:
        m = MetricsResult(
            narrators_enriched=42,
            betweenness_computed=True,
            pagerank_computed=True,
            louvain_computed=False,
            degree_computed=True,
            communities_found=3,
        )
        data = m.model_dump()
        m2 = MetricsResult(**data)
        assert m == m2


class TestTopicResult:
    def test_construction(self) -> None:
        t = TopicResult(
            hadiths_classified=50,
            hadiths_skipped=5,
            model_name="test-model",
            labels_used=["a", "b"],
        )
        assert t.hadiths_classified == 50

    def test_frozen(self) -> None:
        t = TopicResult(
            hadiths_classified=0,
            hadiths_skipped=0,
            model_name="test",
            labels_used=[],
        )
        with pytest.raises(ValidationError):
            t.hadiths_classified = 1  # type: ignore[misc]

    def test_model_dump_roundtrip(self) -> None:
        t = TopicResult(
            hadiths_classified=10,
            hadiths_skipped=2,
            model_name="bart",
            labels_used=TOPIC_LABELS,
        )
        data = t.model_dump()
        t2 = TopicResult(**data)
        assert t == t2


class TestHistoricalResult:
    def test_construction(self) -> None:
        h = HistoricalResult(
            edges_created=100,
            narrators_linked=20,
            events_linked=5,
            narrators_skipped_no_dates=10,
            narrators_skipped_max_lifetime=2,
        )
        assert h.edges_created == 100

    def test_frozen(self) -> None:
        h = HistoricalResult(
            edges_created=0,
            narrators_linked=0,
            events_linked=0,
            narrators_skipped_no_dates=0,
            narrators_skipped_max_lifetime=0,
        )
        with pytest.raises(ValidationError):
            h.edges_created = 1  # type: ignore[misc]

    def test_model_dump_roundtrip(self) -> None:
        h = HistoricalResult(
            edges_created=5,
            narrators_linked=3,
            events_linked=2,
            narrators_skipped_no_dates=1,
            narrators_skipped_max_lifetime=0,
        )
        data = h.model_dump()
        h2 = HistoricalResult(**data)
        assert h == h2


class TestEnrichSummary:
    def test_construction_all_none(self) -> None:
        s = EnrichSummary(
            metrics=None,
            topics=None,
            historical=None,
            steps_completed=[],
            steps_failed=[],
        )
        assert s.metrics is None
        assert s.steps_completed == []

    def test_construction_with_results(self) -> None:
        m = MetricsResult(
            narrators_enriched=10,
            betweenness_computed=True,
            pagerank_computed=True,
            louvain_computed=True,
            degree_computed=True,
            communities_found=2,
        )
        t = TopicResult(
            hadiths_classified=5,
            hadiths_skipped=1,
            model_name="test",
            labels_used=["a"],
        )
        h = HistoricalResult(
            edges_created=3,
            narrators_linked=2,
            events_linked=1,
            narrators_skipped_no_dates=0,
            narrators_skipped_max_lifetime=0,
        )
        s = EnrichSummary(
            metrics=m,
            topics=t,
            historical=h,
            steps_completed=["metrics", "topics", "historical"],
            steps_failed=[],
        )
        assert s.metrics is not None
        assert s.metrics.narrators_enriched == 10
        assert len(s.steps_completed) == 3

    def test_frozen(self) -> None:
        s = EnrichSummary(
            metrics=None,
            topics=None,
            historical=None,
            steps_completed=[],
            steps_failed=[],
        )
        with pytest.raises(ValidationError):
            s.metrics = None  # type: ignore[misc]

    def test_model_dump_roundtrip(self) -> None:
        s = EnrichSummary(
            metrics=None,
            topics=None,
            historical=None,
            steps_completed=["metrics"],
            steps_failed=["topics"],
        )
        data = s.model_dump()
        s2 = EnrichSummary(**data)
        assert s == s2
