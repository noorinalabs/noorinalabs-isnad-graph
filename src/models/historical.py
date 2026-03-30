"""Historical event and location node models for the isnad graph."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import HistoricalEventType

__all__ = ["HistoricalEvent", "Location"]


class HistoricalEvent(BaseModel):
    """A historical event relevant to the context of hadith transmission.

    Events provide temporal anchoring for narrator activity and help
    contextualize the political environment of hadith compilation.
    """

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    id: str
    """Unique identifier for the event."""
    name_en: str
    """English name of the event."""
    name_ar: str | None = None
    """Arabic name of the event."""
    year_start_ah: int
    """Start year in Hijri calendar."""
    year_end_ah: int | None = None
    """End year in Hijri calendar."""
    year_start_ce: int
    """Start year in Common Era calendar."""
    year_end_ce: int | None = None
    """End year in Common Era calendar."""
    event_type: HistoricalEventType = Field(alias="type")
    """Category of the event (serializes as 'type')."""
    caliphate: str | None = None
    """Caliphate during which the event occurred."""
    region: str | None = None
    """Geographic region of the event."""
    description: str | None = None
    """Narrative description of the event."""
    source_url: str | None = None
    """URL of the source from which the event was scraped."""


class Location(BaseModel):
    """A geographic location relevant to narrator biography or hadith transmission."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str
    """Canonical ID with 'loc:' prefix, e.g. 'loc:medina'."""
    name_en: str
    """English name of the location."""
    name_ar: str | None = None
    """Arabic name of the location."""
    region: str | None = None
    """Broader geographic region."""
    lat: float | None = None
    """Latitude coordinate."""
    lon: float | None = None
    """Longitude coordinate."""
    political_entity_period: dict[str, str] | None = None
    """Mapping of date ranges to political entities, e.g. {'622-661': 'Rashidun'}."""
