"""Tests for the canonical hadith topic vocabulary (ig#1061).

Exercises the free-text -> canonical-token mapping, multi-tag de-duplication,
the uncategorized bucket, and the always-present vocabulary in facet aggregation.
"""

from __future__ import annotations

import pytest

from src.utils.topics import (
    TOPIC_LABELS,
    TOPIC_TOKENS,
    UNCATEGORIZED_LABEL,
    UNCATEGORIZED_TOPIC,
    aggregate_topic_facets,
    canonical_topics_for_tags,
    normalize_topic,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("intentions", "akhlaq"),
        ("sincerity", "akhlaq"),
        ("prayer", "ibadah"),
        ("Fasting", "ibadah"),
        ("zakat", "ibadah"),
        ("inheritance", "fiqh"),
        ("Business transactions", "fiqh"),
        ("belief", "aqidah"),
        ("tawhid", "aqidah"),
        ("tafsir", "quran"),
        ("the battle of Badr", "sira"),
        ("seeking knowledge", "knowledge"),
        ("Day of Judgment", "eschatology"),
        ("paradise", "eschatology"),
        ("day_of_judgment", "eschatology"),  # underscore-folded
    ],
)
def test_normalize_topic_maps_freeform_tags(raw: str, expected: str) -> None:
    assert normalize_topic(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", None, "completely unrelated gibberish"])
def test_normalize_topic_returns_none_for_unmapped(raw: str | None) -> None:
    assert normalize_topic(raw) is None


def test_every_canonical_token_has_a_label() -> None:
    assert set(TOPIC_TOKENS) == set(TOPIC_LABELS)
    assert all(TOPIC_LABELS[t] for t in TOPIC_TOKENS)


def test_canonical_topics_dedupes_and_orders() -> None:
    # "prayer" and "supplication" both map to ibadah; "intentions" to akhlaq.
    tags = ["prayer", "supplication", "intentions"]
    result = canonical_topics_for_tags(tags)
    assert result == ["ibadah", "akhlaq"]  # de-duped, in TOPIC_TOKENS order
    # Order is vocabulary order regardless of tag order.
    assert canonical_topics_for_tags(["intentions", "prayer"]) == ["ibadah", "akhlaq"]


@pytest.mark.parametrize("tags", [None, [], ["zzz nonsense"]])
def test_canonical_topics_empty_for_uncategorizable(tags: list[str] | None) -> None:
    assert canonical_topics_for_tags(tags) == []


def test_aggregate_always_returns_full_vocabulary_plus_uncategorized() -> None:
    facets = aggregate_topic_facets([])
    values = [f.value for f in facets]
    assert values == [*TOPIC_TOKENS, UNCATEGORIZED_TOPIC]
    assert all(f.count == 0 for f in facets)
    assert facets[-1].label == UNCATEGORIZED_LABEL


def test_aggregate_counts_per_document_and_uncategorized() -> None:
    facets = aggregate_topic_facets(
        [
            ["intentions", "prayer"],  # akhlaq + ibadah
            ["inheritance"],  # fiqh
            ["prayer"],  # ibadah
            ["obscure tag"],  # uncategorized
            [],  # uncategorized
            None,  # uncategorized
        ]
    )
    counts = {f.value: f.count for f in facets}
    assert counts["ibadah"] == 2
    assert counts["akhlaq"] == 1
    assert counts["fiqh"] == 1
    assert counts["uncategorized"] == 3
    assert counts["eschatology"] == 0


def test_aggregate_counts_a_multi_topic_hadith_once_per_topic() -> None:
    # A single hadith tagged with two synonyms of the same topic counts once
    # for that topic (set semantics), not twice.
    facets = aggregate_topic_facets([["prayer", "salah", "fasting"]])
    counts = {f.value: f.count for f in facets}
    assert counts["ibadah"] == 1
    assert counts["uncategorized"] == 0
