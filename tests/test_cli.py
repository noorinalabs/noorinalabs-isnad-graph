"""Unit tests for CLI argument parsing helpers.

These exercise the pure parsing/plumbing layer of ``src.cli`` without touching
Neo4j/Postgres — the command bodies own the DB work and are covered by the
``src.enrich`` suites. Here we prove the ``embed-hadiths`` collection-scope flags
(#1177) parse into the shapes ``_cmd_embed_hadiths`` expects.
"""

from __future__ import annotations

from src.cli import _split_csv


def test_split_csv_none_is_none() -> None:
    """Flag not supplied → None, so the caller can tell "no scope" from empty."""
    assert _split_csv(None) is None


def test_split_csv_single_value() -> None:
    assert _split_csv("sanadset") == ["sanadset"]


def test_split_csv_multiple_values_trimmed() -> None:
    assert _split_csv("bukhari, muslim ,nasai") == ["bukhari", "muslim", "nasai"]


def test_split_csv_drops_empty_segments() -> None:
    assert _split_csv("bukhari,,  ,muslim") == ["bukhari", "muslim"]


def test_split_csv_all_whitespace_is_none() -> None:
    """An all-blank value collapses to None (keeps the unchanged-default path)."""
    assert _split_csv("   ,  ") is None
