"""Tests for the Loki retention enforcement writer (ig#1038).

Exercises the propagation half of the admin "log retention (days)" control: the
in-place rewrite of Loki's hot-reloadable runtime overrides file. The contract
(deploy#451) requires an in-place truncate write (inode preserved) that touches
only the ``retention_period`` value and is a safe no-op when the runtime volume
is not mounted.
"""

from __future__ import annotations

from pathlib import Path

from src.api.loki_retention import apply_loki_retention, retention_period_for_days

# The deploy-seeded overrides file shape (infra/loki/runtime-overrides.yaml).
_SEED = """\
# Loki runtime overrides — hot-reloadable per-tenant limits (deploy#451).
overrides:
  fake:
    retention_period: 168h  # 7 days (default; admin control overwrites this)
"""


def test_retention_period_for_days() -> None:
    assert retention_period_for_days(7) == "168h"
    assert retention_period_for_days(30) == "720h"
    assert retention_period_for_days(1) == "24h"


def test_rewrites_value_in_place(tmp_path: Path) -> None:
    target = tmp_path / "overrides.yaml"
    target.write_text(_SEED, encoding="utf-8")
    inode_before = target.stat().st_ino

    assert apply_loki_retention(30, path=target) is True

    text = target.read_text(encoding="utf-8")
    assert "retention_period: 720h" in text
    assert "168h" not in text
    # Inode preserved (truncate-write, not rename-replace) so loki's volume view holds.
    assert target.stat().st_ino == inode_before


def test_preserves_surrounding_structure(tmp_path: Path) -> None:
    target = tmp_path / "overrides.yaml"
    target.write_text(_SEED, encoding="utf-8")

    apply_loki_retention(14, path=target)

    text = target.read_text(encoding="utf-8")
    # Comment header, tenant id, and indentation are untouched.
    assert text.startswith("# Loki runtime overrides")
    assert "overrides:\n  fake:\n" in text
    assert "    retention_period: 336h" in text


def test_noop_when_dir_absent(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-dir" / "overrides.yaml"
    assert apply_loki_retention(30, path=missing) is False


def test_noop_when_file_absent(tmp_path: Path) -> None:
    target = tmp_path / "overrides.yaml"  # dir exists, file does not
    assert apply_loki_retention(30, path=target) is False


def test_noop_when_key_missing_does_not_corrupt(tmp_path: Path) -> None:
    target = tmp_path / "overrides.yaml"
    body = "overrides:\n  fake:\n    ingestion_rate_mb: 8\n"
    target.write_text(body, encoding="utf-8")

    assert apply_loki_retention(30, path=target) is False
    # File left untouched, not half-written.
    assert target.read_text(encoding="utf-8") == body
