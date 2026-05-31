"""Hadith node model for the isnad graph."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.enums import SourceCorpus

__all__ = ["Hadith"]


class Hadith(BaseModel):
    """A single hadith (prophetic tradition) with its matn and metadata.

    The hadith is the atomic unit of the graph: chains, gradings, and
    collection appearances all reference a specific hadith node.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str
    """Canonical ID with 'hdt:' prefix, e.g. 'hdt:bukhari-001-001'."""
    matn_ar: str
    """Arabic body text of the hadith."""
    matn_en: str | None = None
    """English translation of the body text."""
    isnad_raw_ar: str | None = None
    """Raw Arabic isnad string."""
    isnad_raw_en: str | None = None
    """Raw English isnad string."""
    grade_composite: str | None = None
    """Consensus or primary grade string."""
    topic_tags: list[str] = Field(default_factory=list)
    """Topic tags populated in Phase 4."""
    chapter_name_ar: str | None = None
    """Arabic chapter (bab) title for the hadith's location in its collection."""
    chapter_name_en: str | None = None
    """English chapter (bab) title for the hadith's location in its collection."""
    source_corpus: SourceCorpus
    """Source corpus from which this hadith was acquired."""
    has_shia_parallel: bool = False
    """Whether a parallel exists in Shia collections."""
    has_sunni_parallel: bool = False
    """Whether a parallel exists in Sunni collections."""

    @field_validator("id")
    @classmethod
    def _validate_id_prefix(cls, v: str) -> str:
        if not v.startswith("hdt:"):
            msg = f"Hadith id must start with 'hdt:', got '{v}'"
            raise ValueError(msg)
        return v
