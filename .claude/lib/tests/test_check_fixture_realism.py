"""Tests for check_fixture_realism — the Production-Realistic fixture lint (#735).

Per the rule it enforces, this test's OWN fixtures are production-realistic:

  - POSITIVE cases are real-shape voweled Arabic isnad chains carrying عَنْ (the
    عن particle, voweled) — e.g. the Bukhari mu`allaq chain shape
    `حَدَّثَنَا … عَنْ … عَنْ …`.
  - NEGATIVE cases are the exact toy shapes the rule flags: an un-voweled blob,
    and the da#146/da#155 worked example — a voweled Bukhari-h1-shape chain that
    is missing عن (the gap that masked the over-segmentation bug).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_fixture_realism import (  # noqa: E402
    check_fixture_text,
    has_an_particle,
    has_arabic_letters,
    has_vocalization,
    main,
    strip_diacritics,
)

# Real-shape voweled isnad with the عَنْ particle (Bukhari-style mu`an`an chain).
# Production-realistic: full harakat + repeated عَنْ, exactly what a naive
# segmenter over-splits.
REAL_VOWELED_WITH_AN = (
    "حَدَّثَنَا مُسَدَّدٌ قَالَ حَدَّثَنَا يَحْيَى عَنْ شُعْبَةَ عَنْ قَتَادَةَ عَنْ أَنَسٍ عَنِ النَّبِيِّ صَلَّى اللَّهُ عَلَيْهِ وَسَلَّمَ"
)

# da#146/da#155 worked example: a voweled Bukhari-h1-shape chain that uses only
# قَالَ / سَمِعَ and carries NO عن — the fixture that masked the over-segmentation.
VOWELED_MISSING_AN = "حَدَّثَنَا الْحُمَيْدِيُّ قَالَ حَدَّثَنَا سُفْيَانُ قَالَ سَمِعْتُ يَحْيَى بْنَ سَعِيدٍ الْأَنْصَارِيَّ"

# Un-voweled toy blob: no diacritics at all (and no عن).
UNVOWELED_TOY = "حدثنا محمد قال حدثنا يحيى بن سعيد"

# Un-voweled but DOES contain عن — isolates the "no vocalization" reason.
UNVOWELED_WITH_AN = "حدثنا محمد عن يحيى عن انس عن النبي"


class HelperPrimitives(unittest.TestCase):
    def test_has_arabic_letters_true_on_arabic(self) -> None:
        self.assertTrue(has_arabic_letters(REAL_VOWELED_WITH_AN))

    def test_has_arabic_letters_false_on_ascii(self) -> None:
        self.assertFalse(has_arabic_letters("hadithReference: 1\nnarrator: Anas"))

    def test_has_vocalization_distinguishes_voweled(self) -> None:
        self.assertTrue(has_vocalization(REAL_VOWELED_WITH_AN))
        self.assertFalse(has_vocalization(UNVOWELED_TOY))

    def test_strip_diacritics_collapses_voweled_an(self) -> None:
        # عَنْ must collapse to bare عن so the particle search can see it.
        self.assertIn("عن", strip_diacritics("عَنْ"))

    def test_has_an_particle_sees_through_vowels(self) -> None:
        # The load-bearing case: voweled عَنْ is detected as the particle.
        self.assertTrue(has_an_particle(REAL_VOWELED_WITH_AN))
        self.assertTrue(has_an_particle(UNVOWELED_WITH_AN))
        self.assertFalse(has_an_particle(VOWELED_MISSING_AN))
        self.assertFalse(has_an_particle(UNVOWELED_TOY))


class CleanFixturesPass(unittest.TestCase):
    def test_real_voweled_chain_with_an_passes(self) -> None:
        self.assertEqual(check_fixture_text("fix.json", REAL_VOWELED_WITH_AN), [])

    def test_non_arabic_file_is_skipped(self) -> None:
        # English / schema-only files are not Arabic-text fixtures — not judged.
        self.assertEqual(check_fixture_text("schema.json", '{"narrator": "Anas", "n": 1}'), [])

    def test_real_chain_embedded_in_json_passes(self) -> None:
        payload = f'{{"matn_ar": "...", "isnad_ar": "{REAL_VOWELED_WITH_AN}"}}'
        self.assertEqual(check_fixture_text("hadith.json", payload), [])


class ToyFixturesFlagged(unittest.TestCase):
    def test_unvoweled_toy_flags_both_reasons(self) -> None:
        violations = check_fixture_text("toy.json", UNVOWELED_TOY)
        self.assertEqual(len(violations), 1)
        self.assertIn("no vocalization diacritics", violations[0])
        self.assertIn("missing transmission particle", violations[0])

    def test_voweled_missing_an_flags_only_particle(self) -> None:
        # The da#146/da#155 shape: voweled (passes a) but no عن (fails b).
        violations = check_fixture_text("bukhari_h1.json", VOWELED_MISSING_AN)
        self.assertEqual(len(violations), 1)
        self.assertNotIn("no vocalization diacritics", violations[0])
        self.assertIn("missing transmission particle", violations[0])

    def test_unvoweled_with_an_flags_only_vocalization(self) -> None:
        violations = check_fixture_text("toy2.json", UNVOWELED_WITH_AN)
        self.assertEqual(len(violations), 1)
        self.assertIn("no vocalization diacritics", violations[0])
        self.assertNotIn("missing transmission particle", violations[0])

    def test_path_reported_in_violation(self) -> None:
        violations = check_fixture_text("fixtures/toy.json", UNVOWELED_TOY)
        self.assertTrue(violations[0].startswith("fixtures/toy.json:"))


class CliBehavior(unittest.TestCase):
    def _write(self, text: str) -> str:
        fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        fh.write(text)
        fh.close()
        return fh.name

    def test_clean_fixture_exits_zero(self) -> None:
        name = self._write(REAL_VOWELED_WITH_AN)
        try:
            self.assertEqual(main(["check_fixture_realism.py", name]), 0)
        finally:
            Path(name).unlink()

    def test_toy_fixture_exits_one(self) -> None:
        name = self._write(UNVOWELED_TOY)
        try:
            self.assertEqual(main(["check_fixture_realism.py", name]), 1)
        finally:
            Path(name).unlink()

    def test_non_arabic_fixture_exits_zero(self) -> None:
        name = self._write('{"narrator": "Anas"}')
        try:
            self.assertEqual(main(["check_fixture_realism.py", name]), 0)
        finally:
            Path(name).unlink()

    def test_no_args_is_usage_error(self) -> None:
        self.assertEqual(main(["check_fixture_realism.py"]), 2)

    def test_missing_file_is_error(self) -> None:
        self.assertEqual(main(["check_fixture_realism.py", "/no/such/fixture.json"]), 2)


if __name__ == "__main__":
    unittest.main()
