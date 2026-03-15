"""Pydantic result models for Phase 4 enrichment operations."""

from pydantic import BaseModel, ConfigDict

__all__ = ["HistoricalResult"]


class HistoricalResult(BaseModel):
    """Result of historical overlay (ACTIVE_DURING edge creation)."""

    model_config = ConfigDict(frozen=True)

    edges_created: int
    narrators_linked: int
    events_linked: int
    narrators_skipped_no_dates: int
    narrators_skipped_max_lifetime: int
