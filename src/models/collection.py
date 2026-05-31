"""Collection node model for the isnad graph."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from src.models.enums import Sect, SourceCorpus

__all__ = ["Collection"]


class Collection(BaseModel):
    """A hadith collection (e.g. Sahih al-Bukhari, al-Kafi).

    Represents a compiled book of hadiths with metadata about its
    compiler, sectarian tradition, and canonical status.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str
    """Canonical ID with 'col:' prefix, e.g. 'col:bukhari'."""
    name_ar: str
    """Arabic title of the collection."""
    name_en: str
    """English title of the collection."""
    compiler_name: str | None = None
    """Human-readable name of the compiler."""
    compiler_id: str | None = None
    """FK to Narrator.id, nullable."""
    compilation_year_ah: int | None = None
    """Year of compilation in Hijri calendar."""
    sect: Sect
    """Sectarian tradition (Sunni or Shia)."""
    source_corpus: SourceCorpus
    """Source corpus from which this collection was acquired."""
    canonical_rank: int | None = None
    """Canonical rank within its tradition (1 = highest authority)."""
    total_hadiths: int | None = None
    """Total number of hadiths in the collection."""
    book_count: int | None = None
    """Number of books/chapters in the collection."""

    @field_validator("id")
    @classmethod
    def _validate_id_prefix(cls, v: str) -> str:
        if not v.startswith("col:"):
            msg = f"Collection id must start with 'col:', got '{v}'"
            raise ValueError(msg)
        return v
