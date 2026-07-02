#!/usr/bin/env python3
"""Thin CLI wrapper for the semantic-search endpoint smoke check (ig#1148).

The testable implementation lives in the installed ``src`` package
(``src.api.semantic_smoke``) so it is importable by pytest and covered by
ruff/mypy; this wrapper only exposes it as a ``scripts/`` entry point for the
deploy smoke and manual promotion-window verification.

Usage:
    uv run python scripts/semantic_smoke.py https://isnad.noorinalabs.com
"""

from __future__ import annotations

import sys

from src.api.semantic_smoke import main

if __name__ == "__main__":
    sys.exit(main())
