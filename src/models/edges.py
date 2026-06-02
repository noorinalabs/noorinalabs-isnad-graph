"""Edge/relationship models for the isnad graph.

These are lightweight validation models for edge data serialization,
not Neo4j relationship objects directly.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.models.enums import TransmissionMethod, VariantType

__all__ = [
    "ActiveDuring",
    "AppearsIn",
    "BasedIn",
    "GradedBy",
    "Narrated",
    "ParallelOf",
    "StudiedUnder",
    "TransmittedTo",
]


class TransmittedTo(BaseModel):
    """Edge: one narrator transmitted a hadith to another in a chain."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    from_narrator_id: str
    """ID of the transmitting narrator."""
    to_narrator_id: str
    """ID of the receiving narrator."""
    hadith_id: str
    """FK to Hadith.id."""
    chain_id: str
    """FK to Chain.id."""
    position_in_chain: int
    """0-based position of this link in the chain."""
    transmission_method: TransmissionMethod
    """Method of transmission (haddathana, an, etc.)."""


class AppearsIn(BaseModel):
    """Edge: a hadith appears in a collection at a specific location."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    hadith_id: str
    """FK to Hadith.id."""
    collection_id: str
    """FK to Collection.id."""
    book_number: int | None = None
    """Book number within the collection."""
    chapter_number: int | None = None
    """Chapter number within the book."""
    hadith_number_in_book: int | None = None
    """Hadith number within the book."""


class ParallelOf(BaseModel):
    """Edge: two hadiths are textual parallels (same or similar matn)."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    hadith_id_a: str
    """First hadith ID."""
    hadith_id_b: str
    """Second hadith ID."""
    similarity_score: float
    """Textual similarity score between 0.0 and 1.0."""
    variant_type: VariantType
    """Type of textual relationship."""
    cross_sect: bool
    """Whether the parallel crosses sectarian boundaries."""


class StudiedUnder(BaseModel):
    """Edge: a narrator studied under (was a student of) another narrator."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    student_id: str
    """ID of the student narrator."""
    teacher_id: str
    """ID of the teacher narrator."""
    period_ah: str | None = None
    """Period of study in Hijri years."""
    location_id: str | None = None
    """FK to Location.id where the study took place."""
    source: str | None = None
    """Bibliographic source documenting this relationship."""


class ActiveDuring(BaseModel):
    """Edge: a narrator was active during a historical event."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    narrator_id: str
    """FK to Narrator.id."""
    event_id: str
    """FK to HistoricalEvent.id."""
    role: str | None = None
    """Role the narrator played during the event."""
    affiliation: str | None = None
    """Political or theological affiliation during the event."""


class Narrated(BaseModel):
    """Edge: a narrator narrated (was the originating source of) a hadith.

    Establishes the schema contract for the ``NARRATED`` relationship
    (narrator -> hadith). The graph-loading emitter is not yet implemented in
    this repo; the relationship is currently merged with no typed properties.
    Defining the model now lets the property allow-list be tightened once the
    loader lands.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    narrator_id: str
    """FK to Narrator.id — the narrator who narrated the hadith."""
    hadith_id: str
    """FK to Hadith.id — the hadith that was narrated."""


class BasedIn(BaseModel):
    """Edge: a narrator was based in a location during a period."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    narrator_id: str
    """FK to Narrator.id."""
    location_id: str
    """FK to Location.id."""
    period_ah: str | None = None
    """Period of residence in Hijri years."""
    role: str | None = None
    """Role or activity at this location."""


class GradedBy(BaseModel):
    """Edge: a hadith was assigned a grading.

    Mirrors the ``GRADED_BY`` relationship (hadith -> grading) emitted by the
    ingest-platform normalize stage — ``workers/normalize/processor.py``
    appends an ``_EdgeRow(label="GRADED_BY", src_label="Hadith",
    dst_label="Grading", props={})`` whenever a grade is present. The emitter
    carries no typed edge properties today; this model establishes the schema
    contract so ingest-platform can tighten its ``GRADED_BY`` property
    allow-list to match.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    hadith_id: str
    """FK to Hadith.id — the hadith that was graded."""
    grading_id: str
    """FK to Grading.id — the grading assigned to the hadith."""
