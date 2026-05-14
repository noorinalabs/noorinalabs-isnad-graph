"""Frozen Pydantic v2 models for all graph nodes and edges.

All models use ConfigDict(frozen=True) for immutability and
all enums inherit from (str, Enum) for clean serialization.
"""

from src.models.chain import Chain
from src.models.collection import Collection
from src.models.edges import (
    ActiveDuring,
    AppearsIn,
    BasedIn,
    Narrated,
    ParallelOf,
    StudiedUnder,
    TransmittedTo,
)
from src.models.enums import (
    ChainClassification,
    ChainPosition,
    Gender,
    HadithGrade,
    HistoricalEventType,
    NarratorGeneration,
    NarratorRole,
    Sect,
    SectAffiliation,
    SourceCorpus,
    TransmissionMethod,
    TrustworthinessGrade,
    VariantType,
)
from src.models.grading import Grading
from src.models.hadith import Hadith
from src.models.historical import HistoricalEvent, Location
from src.models.narrator import Narrator

__all__ = [
    # Enums
    "ChainClassification",
    "ChainPosition",
    "Gender",
    "HadithGrade",
    "HistoricalEventType",
    "NarratorGeneration",
    "NarratorRole",
    "Sect",
    "SectAffiliation",
    "SourceCorpus",
    "TransmissionMethod",
    "TrustworthinessGrade",
    "VariantType",
    # Node models
    "Chain",
    "Collection",
    "Grading",
    "Hadith",
    "HistoricalEvent",
    "Location",
    "Narrator",
    # Edge models
    "ActiveDuring",
    "AppearsIn",
    "BasedIn",
    "Narrated",
    "ParallelOf",
    "StudiedUnder",
    "TransmittedTo",
]
