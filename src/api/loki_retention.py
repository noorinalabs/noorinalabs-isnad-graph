"""Loki retention enforcement for the admin "log retention (days)" control (ig#1038).

The admin Config panel persists ``log_retention_days`` to Postgres (source of
truth). This module is the propagation half: it rewrites Loki's hot-reloadable
``runtime_config`` overrides file so the new window takes effect *without a Loki
restart*. The deploy side (deploy#451) wires the file:

- ``loki-config.yml`` enables ``runtime_config`` with ``period: 30s`` — Loki
  re-reads the overrides file every 30s and the compactor applies any changed
  ``retention_period`` on its next compaction cycle.
- The ``loki_runtime`` volume is mounted **read-write into the api container** at
  ``/etc/loki/runtime`` precisely so this code can write the value, and
  **read-side into loki** at the same path.

Contract details that this writer honours:

- **In-place truncate write, never rename-replace.** The overrides file is a
  bind/volume view; ``os.replace`` would swap the inode and break loki's view.
  ``open(path, "w")`` truncates the existing inode in place — exactly right.
- **Surgical line rewrite.** Only the ``retention_period`` value is changed so
  the deploy-seeded comments, tenant id, and any other limits are preserved.
- **Best-effort.** When the runtime volume is not mounted (local/dev/test) the
  write is a logged no-op; the DB-persisted value remains authoritative and Loki
  falls back to its static ``limits_config.retention_period`` (7d).
"""

from __future__ import annotations

import re
from pathlib import Path

from src.config import get_settings
from src.utils.logging import get_logger

log = get_logger(__name__)

__all__ = ["apply_loki_retention", "retention_period_for_days"]

# Matches the single ``retention_period:`` line in the overrides file, capturing
# its indentation so we can rewrite the value while preserving structure.
_RETENTION_LINE_RE = re.compile(
    r"^(?P<indent>[ \t]*)retention_period:[ \t]*\S.*$",
    re.MULTILINE,
)


def retention_period_for_days(days: int) -> str:
    """Convert a day count to the hour-suffixed duration Loki expects (e.g. ``"720h"``)."""
    return f"{days * 24}h"


def apply_loki_retention(days: int, *, path: str | Path | None = None) -> bool:
    """Rewrite the Loki runtime overrides file with the new retention window.

    Returns ``True`` when the file was rewritten, ``False`` when the write was a
    best-effort no-op (volume/file absent, key missing, or an OS error). Never
    raises — log retention is a propagation concern and must not fail the admin
    config update whose DB write is the source of truth.
    """
    target = Path(path) if path is not None else Path(get_settings().loki.runtime_overrides_path)
    period = retention_period_for_days(days)

    if not target.parent.exists():
        log.warning(
            "loki_retention_skipped",
            reason="runtime overrides dir absent (loki_runtime volume not mounted)",
            path=str(target),
        )
        return False
    if not target.exists():
        log.warning("loki_retention_skipped", reason="overrides file absent", path=str(target))
        return False

    try:
        original = target.read_text(encoding="utf-8")
        new_text, n = _RETENTION_LINE_RE.subn(
            lambda m: (
                f"{m.group('indent')}retention_period: {period}"
                "  # set via admin Config — log retention (days), ig#1038"
            ),
            original,
            count=1,
        )
        if n == 0:
            log.warning(
                "loki_retention_skipped",
                reason="no retention_period key found in overrides file",
                path=str(target),
            )
            return False
        # In-place truncate write — preserves the inode the loki volume view tracks.
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(new_text)
    except OSError as exc:
        log.warning("loki_retention_write_failed", path=str(target), error=str(exc))
        return False

    log.info("loki_retention_applied", path=str(target), retention_period=period, days=days)
    return True
