"""Tests for Arabic text processing utilities."""

from __future__ import annotations

import pytest

from src.utils.arabic import (
    clean_whitespace,
    extract_transmission_phrases,
    is_arabic,
    normalize_alif,
    normalize_arabic,
    normalize_hamza,
    normalize_taa_marbuta,
    strip_diacritics,
)

# ---------------------------------------------------------------------------
# strip_diacritics
# ---------------------------------------------------------------------------


class TestStripDiacritics:
    def test_basmala(self) -> None:
        assert strip_diacritics("بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ") == "بسم الله الرحمن الرحيم"

    def test_no_diacritics_unchanged(self) -> None:
        plain = "بسم الله"
        assert strip_diacritics(plain) == plain

    def test_empty_string(self) -> None:
        assert strip_diacritics("") == ""

    def test_diacritics_only(self) -> None:
        """A string of only diacritics should produce an empty string."""
        diacritics = "\u064b\u064c\u064d\u064e\u064f\u0650"
        assert strip_diacritics(diacritics) == ""

    def test_latin_text_unchanged(self) -> None:
        assert strip_diacritics("Hello World") == "Hello World"


# ---------------------------------------------------------------------------
# normalize_alif
# ---------------------------------------------------------------------------


class TestNormalizeAlif:
    @pytest.mark.parametrize(
        ("input_char", "expected"),
        [
            ("\u0623", "\u0627"),  # أ → ا
            ("\u0625", "\u0627"),  # إ → ا
            ("\u0622", "\u0627"),  # آ → ا
            ("\u0671", "\u0627"),  # ٱ → ا
        ],
        ids=["hamza-above", "hamza-below", "madda", "wasla"],
    )
    def test_individual_variants(self, input_char: str, expected: str) -> None:
        assert normalize_alif(input_char) == expected

    def test_within_word(self) -> None:
        assert normalize_alif("أحمد") == "احمد"

    def test_bare_alif_unchanged(self) -> None:
        assert normalize_alif("ا") == "ا"

    def test_empty_string(self) -> None:
        assert normalize_alif("") == ""


# ---------------------------------------------------------------------------
# normalize_hamza
# ---------------------------------------------------------------------------


class TestNormalizeHamza:
    def test_hamza_on_waw(self) -> None:
        assert normalize_hamza("ؤ") == "ء"

    def test_hamza_on_ya(self) -> None:
        assert normalize_hamza("ئ") == "ء"

    def test_in_word(self) -> None:
        assert normalize_hamza("مؤمن") == "مءمن"

    def test_empty_string(self) -> None:
        assert normalize_hamza("") == ""


# ---------------------------------------------------------------------------
# normalize_taa_marbuta
# ---------------------------------------------------------------------------


class TestNormalizeTaaMarbuta:
    def test_basic(self) -> None:
        assert normalize_taa_marbuta("ة") == "ه"

    def test_in_word(self) -> None:
        assert normalize_taa_marbuta("مدينة") == "مدينه"

    def test_empty_string(self) -> None:
        assert normalize_taa_marbuta("") == ""


# ---------------------------------------------------------------------------
# clean_whitespace
# ---------------------------------------------------------------------------


class TestCleanWhitespace:
    def test_multiple_spaces(self) -> None:
        assert clean_whitespace("أبو   هريرة") == "أبو هريرة"

    def test_leading_trailing(self) -> None:
        assert clean_whitespace("  بسم الله  ") == "بسم الله"

    def test_tabs_newlines(self) -> None:
        assert clean_whitespace("hello\t\nworld") == "hello world"

    def test_empty_string(self) -> None:
        assert clean_whitespace("") == ""


# ---------------------------------------------------------------------------
# normalize_arabic (full pipeline)
# ---------------------------------------------------------------------------


class TestNormalizeArabic:
    def test_full_pipeline(self) -> None:
        """Diacritics stripped, alif/hamza/taa normalized, tatweel removed, WS collapsed."""
        raw = "  بِسْمِ  اللَّهِ  الرَّحْمَـٰنِ  "
        result = normalize_arabic(raw)
        # Diacritics removed, tatweel removed, whitespace collapsed
        assert "ِ" not in result  # noqa: RUF001
        assert "ـ" not in result
        assert "  " not in result
        assert result == result.strip()

    def test_tatweel_removed(self) -> None:
        assert normalize_arabic("عـلـي") == "علي"

    def test_idempotent(self) -> None:
        """Normalizing already-normalized text returns the same result."""
        text = "بسم الله الرحمن الرحيم"
        assert normalize_arabic(normalize_arabic(text)) == normalize_arabic(text)

    def test_empty_string(self) -> None:
        assert normalize_arabic("") == ""

    def test_mixed_arabic_latin(self) -> None:
        """Latin characters are preserved alongside normalized Arabic."""
        result = normalize_arabic("Hello أحمد World")
        assert "Hello" in result
        assert "World" in result


# ---------------------------------------------------------------------------
# is_arabic
# ---------------------------------------------------------------------------


class TestIsArabic:
    def test_arabic_text(self) -> None:
        assert is_arabic("بسم الله") is True

    def test_english_text(self) -> None:
        assert is_arabic("Hello World") is False

    def test_mixed_text(self) -> None:
        assert is_arabic("Hello أحمد") is True

    def test_empty_string(self) -> None:
        assert is_arabic("") is False

    def test_arabic_diacritics_only(self) -> None:
        """Diacritics (U+064B-U+065F) are within the Arabic block U+0600-U+06FF."""
        assert is_arabic("\u064b\u064c") is True

    def test_numbers_only(self) -> None:
        assert is_arabic("12345") is False


# ---------------------------------------------------------------------------
# extract_transmission_phrases
# ---------------------------------------------------------------------------


class TestExtractTransmissionPhrases:
    def test_haddathana_and_an(self) -> None:
        text = "حدثنا سفيان عن الزهري"
        results = extract_transmission_phrases(text)
        labels = [label for _, _, label in results]
        assert "haddathana" in labels
        assert "an" in labels

    def test_positions_ordered(self) -> None:
        text = "حدثنا سفيان عن الزهري"
        results = extract_transmission_phrases(text)
        starts = [start for start, _, _ in results]
        assert starts == sorted(starts)

    def test_multiple_patterns(self) -> None:
        text = "أخبرنا فلان قال سمعت فلانا"
        results = extract_transmission_phrases(text)
        labels = {label for _, _, label in results}
        assert "akhbarana" in labels
        assert "qala" in labels
        assert "samitu" in labels

    def test_no_matches(self) -> None:
        assert extract_transmission_phrases("Hello World") == []

    def test_empty_string(self) -> None:
        assert extract_transmission_phrases("") == []

    def test_return_type(self) -> None:
        results = extract_transmission_phrases("حدثنا")
        assert len(results) == 1
        start, end, label = results[0]
        assert isinstance(start, int)
        assert isinstance(end, int)
        assert label == "haddathana"
