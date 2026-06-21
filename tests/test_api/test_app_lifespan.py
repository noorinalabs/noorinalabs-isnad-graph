"""Tests for the FastAPI app lifespan — Neo4j wiring and index bootstrap."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from fastapi import FastAPI


@asynccontextmanager
async def _no_settings_cache():  # type: ignore[no-untyped-def]
    """Keep ``get_settings`` cache from leaking real config between tests."""
    from src.config import get_settings

    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


def _patch_neo4j(monkeypatch: pytest.MonkeyPatch, client: MagicMock) -> None:
    """Make the lifespan construct ``client`` instead of a real Neo4jClient."""
    import src.utils.neo4j_client as neo4j_module

    monkeypatch.setattr(neo4j_module, "Neo4jClient", lambda **_: client)


def test_offline_fixture_neutralizes_neo4j_driver() -> None:
    """The autouse offline fixture (``tests/conftest.py``) must stub the neo4j
    driver so a context-managed, unmocked ``TestClient`` — which runs the app
    lifespan and constructs a *real* ``Neo4jClient`` — cannot stall ~60s opening
    a bolt socket under network isolation (ig#1118).

    We assert at the driver entrypoint rather than via a live ~60s connect so
    the guard itself never blocks: with the stub a session probe raises
    ``ServiceUnavailable`` instantly; without it the real (lazy) driver returns
    a session without connecting, so this test fails fast (DID NOT RAISE)
    instead of hanging.
    """
    import neo4j

    driver = neo4j.GraphDatabase.driver("bolt://192.0.2.1:7687", auth=("neo4j", "x"))
    with pytest.raises(neo4j.exceptions.ServiceUnavailable, match="ig#1118"):
        driver.session()


@pytest.mark.asyncio
async def test_lifespan_ensures_fulltext_indexes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup creates the search full-text indexes (idempotent bootstrap)."""
    from src.api.app import lifespan

    fake_client = MagicMock()
    _patch_neo4j(monkeypatch, fake_client)

    app: FastAPI = MagicMock()
    async with _no_settings_cache():
        async with lifespan(app):
            pass

    fake_client.ensure_fulltext_indexes.assert_called_once()
    fake_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_survives_index_bootstrap_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transiently-unavailable Neo4j must not block API startup."""
    from src.api.app import lifespan

    fake_client = MagicMock()
    fake_client.ensure_fulltext_indexes.side_effect = Exception("Neo4j unavailable")
    _patch_neo4j(monkeypatch, fake_client)

    app: FastAPI = MagicMock()
    async with _no_settings_cache():
        # Must not raise despite the index bootstrap failing.
        async with lifespan(app):
            pass

    fake_client.ensure_fulltext_indexes.assert_called_once()
    fake_client.close.assert_called_once()
