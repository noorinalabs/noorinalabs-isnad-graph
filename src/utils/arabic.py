"""Pure-Python Arabic text processing utilities for hadith isnad analysis.

All functions use only ``re`` and ``unicodedata`` from the standard library.
Compiled regex patterns are defined at module level for performance.
"""

from __future__ import annotations

import re

__all__ = [
    "strip_diacritics",
    "normalize_alif",
    "normalize_hamza",
    "normalize_taa_marbuta",
    "normalize_arabic",
    "clean_whitespace",
    "is_arabic",
    "extract_transmission_phrases",
]

# ---------------------------------------------------------------------------
# Compiled regex patterns (module-level for performance)
# ---------------------------------------------------------------------------

# Arabic tashkeel (diacritics): U+064B–U+065F and U+0670 (superscript alef)
_DIACRITICS_RE: re.Pattern[str] = re.compile(r"[\u064B-\u065F\u0670]")

# Alif variants: أ (U+0623), إ (U+0625), آ (U+0622), ٱ (U+0671)
_ALIF_VARIANTS_RE: re.Pattern[str] = re.compile(r"[\u0623\u0625\u0622\u0671]")

# Hamza-on-carrier variants: ؤ (U+0624), ئ (U+0626)
_HAMZA_VARIANTS_RE: re.Pattern[str] = re.compile(r"[\u0624\u0626]")

# Taa marbuta: ة (U+0629)
_TAA_MARBUTA_RE: re.Pattern[str] = re.compile(r"\u0629")

# Tatweel / kashida: ـ (U+0640)
_TATWEEL_RE: re.Pattern[str] = re.compile(r"\u0640")

# Multiple whitespace
_MULTI_WS_RE: re.Pattern[str] = re.compile(r"\s+")

# Arabic script block: U+0600–U+06FF
_ARABIC_CHAR_RE: re.Pattern[str] = re.compile(r"[\u0600-\u06FF]")

# ---------------------------------------------------------------------------
# Transmission phrase patterns
# ---------------------------------------------------------------------------

TRANSMISSION_PATTERNS: dict[re.Pattern[str], str] = {
    re.compile(r"حدثنا"): "haddathana",
    re.compile(r"أخبرنا"): "akhbarana",
    re.compile(r"سمعت"): "samitu",
    re.compile(r"عن"): "an",
    re.compile(r"قال"): "qala",
    re.compile(r"أنبأنا"): "anba_ana",
    re.compile(r"ناولني"): "nawalani",
    re.compile(r"كتب\s+إلي"): "kataba_ilayya",
}

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def strip_diacritics(text: str) -> str:
    """Remove Arabic tashkeel marks (U+064B–U+065F, U+0670)."""
    return _DIACRITICS_RE.sub("", text)


def normalize_alif(text: str) -> str:
    """Normalize أ إ آ ٱ to bare alif ا."""
    return _ALIF_VARIANTS_RE.sub("\u0627", text)


def normalize_hamza(text: str) -> str:
    """Normalize ؤ ئ to standalone hamza ء."""
    return _HAMZA_VARIANTS_RE.sub("\u0621", text)


def normalize_taa_marbuta(text: str) -> str:
    """Normalize ة to ه."""
    return _TAA_MARBUTA_RE.sub("\u0647", text)


def clean_whitespace(text: str) -> str:
    """Collapse multiple whitespace characters to a single space and strip edges."""
    return _MULTI_WS_RE.sub(" ", text).strip()


def normalize_arabic(text: str) -> str:
    """Full Arabic normalization pipeline.

    Steps:
    1. Strip diacritics
    2. Normalize alif variants
    3. Normalize hamza variants
    4. Normalize taa marbuta
    5. Strip tatweel (kashida)
    6. Collapse whitespace
    """
    text = strip_diacritics(text)
    text = normalize_alif(text)
    text = normalize_hamza(text)
    text = normalize_taa_marbuta(text)
    text = _TATWEEL_RE.sub("", text)
    text = clean_whitespace(text)
    return text


def is_arabic(text: str) -> bool:
    """Return True if *text* contains at least one Arabic script character (U+0600–U+06FF)."""
    return bool(_ARABIC_CHAR_RE.search(text))


def extract_transmission_phrases(text: str) -> list[tuple[int, int, str]]:
    """Find transmission formula positions in *text*.

    Returns a list of ``(start, end, label)`` tuples for each non-overlapping
    match found via :data:`TRANSMISSION_PATTERNS`.
    """
    results: list[tuple[int, int, str]] = []
    for pattern, label in TRANSMISSION_PATTERNS.items():
        for match in pattern.finditer(text):
            results.append((match.start(), match.end(), label))
    # Sort by start position for deterministic output
    results.sort(key=lambda t: t[0])
    return results
