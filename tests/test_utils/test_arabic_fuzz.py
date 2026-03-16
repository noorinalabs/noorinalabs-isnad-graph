"""Fuzz testing for Arabic text utilities."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.utils.arabic import (
    extract_transmission_phrases,
    is_arabic,
    normalize_arabic,
    strip_diacritics,
)

# Register Hypothesis profiles for different CI environments.
# Default "ci" profile uses 200 examples; "nightly" uses 1000 for deeper coverage.
# Usage: pytest --hypothesis-profile=nightly
settings.register_profile("ci", max_examples=200)
settings.register_profile(
    "nightly",
    max_examples=1000,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("ci")


class TestArabicFuzz:
    """Property-based fuzz tests ensuring Arabic utilities never crash."""

    @given(st.text(min_size=0, max_size=1000))
    def test_normalize_arabic_never_crashes(self, text: str) -> None:
        """normalize_arabic should handle any string without raising."""
        result = normalize_arabic(text)
        assert isinstance(result, str)

    @given(st.text(min_size=0, max_size=1000))
    def test_strip_diacritics_never_crashes(self, text: str) -> None:
        """strip_diacritics should handle any string without raising."""
        result = strip_diacritics(text)
        assert isinstance(result, str)

    @given(st.text(min_size=0, max_size=1000))
    def test_is_arabic_returns_bool(self, text: str) -> None:
        """is_arabic should always return a bool."""
        result = is_arabic(text)
        assert isinstance(result, bool)

    @given(
        st.text(
            alphabet=st.characters(whitelist_categories=("Lo",)),
            min_size=1,
            max_size=500,
        )
    )
    @settings(max_examples=100)
    def test_extract_transmission_returns_list(self, text: str) -> None:
        """extract_transmission_phrases should always return a list of tuples."""
        result = extract_transmission_phrases(text)
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 3
            start, end, label = item
            assert isinstance(start, int)
            assert isinstance(end, int)
            assert isinstance(label, str)
            assert start >= 0
            assert end > start

    @given(st.text(min_size=0, max_size=1000))
    def test_normalize_is_idempotent(self, text: str) -> None:
        """Applying normalize_arabic twice should give the same result."""
        once = normalize_arabic(text)
        twice = normalize_arabic(once)
        assert once == twice

    @given(st.text(min_size=0, max_size=1000))
    def test_strip_diacritics_is_idempotent(self, text: str) -> None:
        """Applying strip_diacritics twice should give the same result."""
        once = strip_diacritics(text)
        twice = strip_diacritics(once)
        assert once == twice

    def test_unicode_edge_cases(self) -> None:
        """Test specific Unicode edge cases."""
        edge_cases = [
            "",  # empty
            "\u200b",  # zero-width space
            "\u200f",  # right-to-left mark
            "a" * 10000,  # very long
            "\n\t\r",  # whitespace only
            "\u0644\u0645\u062e\u062a\u0644\u0637 mixed",  # mixed Arabic-Latin
            "\u0600",  # Arabic number sign
            "\u06ff",  # end of Arabic block
            "\ud800",  # lone surrogate (may cause issues in some libs)
            "\U0001f600",  # emoji
            "\u0000",  # null character
            "\ufeff",  # BOM
            "\u200e" * 100,  # many LTR marks
            "\u064b\u064c\u064d\u064e\u064f\u0650",  # diacritics only
        ]
        for text in edge_cases:
            try:
                # Should never crash
                normalize_arabic(text)
                strip_diacritics(text)
                result = is_arabic(text)
                assert isinstance(result, bool)
                phrases = extract_transmission_phrases(text)
                assert isinstance(phrases, list)
            except UnicodeEncodeError:
                # Lone surrogates may cause UnicodeEncodeError in some contexts;
                # that's acceptable as long as we don't get an unhandled crash.
                pass
