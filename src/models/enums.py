"""Enum types for the isnad-graph data model.

All enums inherit from StrEnum for clean JSON/Parquet serialization.
"""

from enum import StrEnum

__all__ = [
    "ChainClassification",
    "ChainPosition",
    "DatePrecision",
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
]


class DatePrecision(StrEnum):
    """How tightly a source dates a narrator's birth/death year.

    Mirrors the ``DatePrecision`` contract produced data-acquisition-side
    (da#161) so the resolved earliest/latest bounds carried on a Narrator node
    are never confused with an attested point year. ``precision`` answers "how
    tightly does the *source* date the event"; it is orthogonal to the
    disambiguation ``confidence`` (how sure we are the date attaches to this
    canonical narrator).

    Values:
        ``EXACT``            -- single attested year (earliest == latest == point)
        ``RANGE``            -- attested bounds, e.g. "between 130 and 135"
        ``CIRCA``            -- "~X", a point with a small symmetric window
        ``AFTER``            -- "died after X" → earliest = X, latest unknown
        ``BEFORE``           -- "died before X" → latest = X, earliest unknown
        ``TABAQA_ESTIMATE``  -- no year attested; window derived from the tabaqa
        ``UNKNOWN``          -- nothing is known
    """

    EXACT = "exact"
    RANGE = "range"
    CIRCA = "circa"
    AFTER = "after"
    BEFORE = "before"
    TABAQA_ESTIMATE = "tabaqa_estimate"
    UNKNOWN = "unknown"


class NarratorGeneration(StrEnum):
    """Generation classification of a hadith narrator in the transmission chain."""

    SAHABI = "sahabi"
    TABII = "tabii"
    TABA_TABII = "taba_tabii"
    ATBA_TABA_TABIIN = "atba_taba_tabiin"
    LATER = "later"
    UNKNOWN = "unknown"


class Gender(StrEnum):
    """Biological gender of a narrator."""

    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class SectAffiliation(StrEnum):
    """Sectarian affiliation of a narrator as determined by biographical sources."""

    SUNNI = "sunni"
    SHIA = "shia"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class TrustworthinessGrade(StrEnum):
    """Narrator trustworthiness grade from classical rijal criticism."""

    THIQA = "thiqa"
    SADUQ = "saduq"
    MAQBUL = "maqbul"
    DAIF = "daif"
    MATRUK = "matruk"
    KADHDHAB = "kadhdhab"
    UNKNOWN = "unknown"


class HadithGrade(StrEnum):
    """Overall authenticity grade assigned to a hadith."""

    SAHIH = "sahih"
    HASAN = "hasan"
    DAIF = "daif"
    MAWDU = "mawdu"
    SAHIH_LI_GHAYRIHI = "sahih_li_ghayrihi"
    HASAN_LI_GHAYRIHI = "hasan_li_ghayrihi"
    UNKNOWN = "unknown"


class TransmissionMethod(StrEnum):
    """Method of hadith transmission between narrators."""

    HADDATHANA = "haddathana"
    AKHBARANA = "akhbarana"
    SAMITU = "samitu"
    AN = "an"
    QALA = "qala"
    ANBA_ANA = "anba_ana"
    NAWALANI = "nawalani"
    KATABA_ILAYYA = "kataba_ilayya"
    WIJADA = "wijada"
    OTHER = "other"
    UNKNOWN = "unknown"


class ChainClassification(StrEnum):
    """Classification of an isnad chain's continuity and reliability."""

    MUTTASIL = "muttasil"
    MURSAL = "mursal"
    MUALLAQ = "muallaq"
    MUNQATI = "munqati"
    MUDALLAS = "mudallas"
    MUDTARIB = "mudtarib"
    UNKNOWN = "unknown"


class ChainPosition(StrEnum):
    """Position of a narrator within a chain of transmission."""

    ORIGINATOR = "originator"
    FIRST = "first"
    MIDDLE = "middle"
    LAST = "last"
    UNKNOWN = "unknown"


class NarratorRole(StrEnum):
    """Role of a narrator in the hadith transmission ecosystem."""

    ORIGINATOR = "originator"
    TRANSMITTER = "transmitter"
    COMPILER = "compiler"


class VariantType(StrEnum):
    """Type of textual relationship between parallel hadiths."""

    VERBATIM = "verbatim"
    CLOSE_PARAPHRASE = "close_paraphrase"
    THEMATIC = "thematic"
    CONTRADICTORY = "contradictory"


class HistoricalEventType(StrEnum):
    """Category of historical event relevant to hadith transmission context."""

    CALIPHATE = "caliphate"
    FITNA = "fitna"
    CONQUEST = "conquest"
    THEOLOGICAL_CONTROVERSY = "theological_controversy"
    COMPILATION_EFFORT = "compilation_effort"
    PERSECUTION = "persecution"
    DYNASTY_TRANSITION = "dynasty_transition"


class SourceCorpus(StrEnum):
    """Identifier for the source corpus from which data was acquired."""

    LK = "lk"
    SANADSET = "sanadset"
    THAQALAYN = "thaqalayn"
    SUNNAH = "sunnah"
    FAWAZ = "fawaz"
    OPEN_HADITH = "open_hadith"
    MUHADDITHAT = "muhaddithat"


class Sect(StrEnum):
    """Islamic sectarian tradition."""

    SUNNI = "sunni"
    SHIA = "shia"
