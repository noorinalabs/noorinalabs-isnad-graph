"""Tests for src.resolve.disambiguate — 5-stage disambiguation pipeline."""

from __future__ import annotations

import uuid

import pytest

from src.resolve.disambiguate import (
    _CANONICAL_NAMESPACE,
    Candidate,
    ChainContext,
    Match,
    _build_blocking_index,
    _crossref_match,
    _crossref_match_blocked,
    _exact_match,
    _exact_match_indexed,
    _fuzzy_match,
    _fuzzy_match_blocked,
    _geographic_filter,
    _make_canonical_id,
    _temporal_filter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def candidate_abu_hurayra() -> Candidate:
    return Candidate(
        bio_id="bio-001",
        name_ar="\u0623\u0628\u0648 \u0647\u0631\u064a\u0631\u0629",
        name_en="Abu Hurayra",
        name_ar_normalized="\u0627\u0628\u0648 \u0647\u0631\u064a\u0631\u0647",
        death_year_ah=59,
        external_id="ms-001",
        source="muhaddithat",
    )


@pytest.fixture
def candidate_anas() -> Candidate:
    return Candidate(
        bio_id="bio-002",
        name_ar="\u0623\u0646\u0633 \u0628\u0646 \u0645\u0627\u0644\u0643",
        name_en="Anas ibn Malik",
        name_ar_normalized="\u0627\u0646\u0633 \u0628\u0646 \u0645\u0627\u0644\u0643",
        death_year_ah=93,
        external_id=None,
        source="muhaddithat",
    )


@pytest.fixture
def candidate_no_temporal() -> Candidate:
    return Candidate(
        bio_id="bio-003",
        name_ar="\u0639\u0644\u064a",
        name_en="Ali",
        name_ar_normalized="\u0639\u0644\u064a",
        death_year_ah=None,
        external_id=None,
        source="muhaddithat",
    )


@pytest.fixture
def candidates(
    candidate_abu_hurayra: Candidate,
    candidate_anas: Candidate,
    candidate_no_temporal: Candidate,
) -> list[Candidate]:
    return [candidate_abu_hurayra, candidate_anas, candidate_no_temporal]


# ---------------------------------------------------------------------------
# Stage 1: Exact match
# ---------------------------------------------------------------------------
class TestExactMatch:
    def test_exact_arabic_match(self, candidates: list[Candidate]) -> None:
        matches = _exact_match("\u0627\u0628\u0648 \u0647\u0631\u064a\u0631\u0647", candidates)
        assert len(matches) == 1
        assert matches[0].stage == "exact"
        assert matches[0].score == 1.0
        assert matches[0].candidate.bio_id == "bio-001"

    def test_exact_english_match(self, candidates: list[Candidate]) -> None:
        matches = _exact_match("Abu Hurayra", candidates)
        assert len(matches) == 1
        assert matches[0].candidate.name_en == "Abu Hurayra"

    def test_no_match(self, candidates: list[Candidate]) -> None:
        matches = _exact_match("unknown narrator", candidates)
        assert matches == []

    def test_empty_mention(self, candidates: list[Candidate]) -> None:
        matches = _exact_match("", candidates)
        assert matches == []


# ---------------------------------------------------------------------------
# Stage 2: Fuzzy match
# ---------------------------------------------------------------------------
class TestFuzzyMatch:
    def test_similar_name_matches(self, candidates: list[Candidate]) -> None:
        # One-char difference from normalized name should match (Levenshtein <= 2).
        matches = _fuzzy_match("\u0627\u0628\u0648 \u0647\u0631\u064a\u0631\u0629", candidates)
        assert len(matches) >= 1
        assert all(m.stage == "fuzzy" for m in matches)
        assert all(0 < m.score <= 1.0 for m in matches)

    def test_distant_name_no_match(self, candidates: list[Candidate]) -> None:
        matches = _fuzzy_match("completely different name", candidates)
        assert matches == []

    def test_empty_mention(self, candidates: list[Candidate]) -> None:
        matches = _fuzzy_match("", candidates)
        assert matches == []


# ---------------------------------------------------------------------------
# Stage 3: Temporal filter
# ---------------------------------------------------------------------------
class TestTemporalFilter:
    def test_valid_gap_passes(self, candidate_abu_hurayra: Candidate) -> None:
        match = Match(candidate=candidate_abu_hurayra, stage="fuzzy", score=0.85)
        ctx = ChainContext(
            hadith_id="h-1",
            position_in_chain=0,
            source_corpus="test",
            adjacent_death_years=[30],  # gap = |59 - 30| = 29, within 15-80
        )
        filtered = _temporal_filter([match], ctx)
        assert len(filtered) == 1

    def test_invalid_gap_filtered_out(self, candidate_abu_hurayra: Candidate) -> None:
        match = Match(candidate=candidate_abu_hurayra, stage="fuzzy", score=0.85)
        ctx = ChainContext(
            hadith_id="h-1",
            position_in_chain=0,
            source_corpus="test",
            adjacent_death_years=[55],  # gap = |59 - 55| = 4, below 15
        )
        filtered = _temporal_filter([match], ctx)
        assert len(filtered) == 0

    def test_no_adjacent_years_passes_all(self, candidate_abu_hurayra: Candidate) -> None:
        match = Match(candidate=candidate_abu_hurayra, stage="fuzzy", score=0.85)
        ctx = ChainContext(
            hadith_id="h-1",
            position_in_chain=0,
            source_corpus="test",
            adjacent_death_years=[],
        )
        filtered = _temporal_filter([match], ctx)
        assert len(filtered) == 1

    def test_candidate_no_death_year_passes(self, candidate_no_temporal: Candidate) -> None:
        match = Match(candidate=candidate_no_temporal, stage="fuzzy", score=0.80)
        ctx = ChainContext(
            hadith_id="h-1",
            position_in_chain=0,
            source_corpus="test",
            adjacent_death_years=[100],
        )
        filtered = _temporal_filter([match], ctx)
        assert len(filtered) == 1


# ---------------------------------------------------------------------------
# Stage 4: Geographic filter
# ---------------------------------------------------------------------------
class TestGeographicFilter:
    def test_passthrough(self, candidate_abu_hurayra: Candidate) -> None:
        matches = [Match(candidate=candidate_abu_hurayra, stage="fuzzy", score=0.85)]
        filtered = _geographic_filter(matches)
        assert filtered == matches

    def test_empty_list(self) -> None:
        assert _geographic_filter([]) == []


# ---------------------------------------------------------------------------
# Stage 5: Cross-reference match
# ---------------------------------------------------------------------------
class TestCrossrefMatch:
    def test_external_id_boosts_match(self, candidates: list[Candidate]) -> None:
        # candidate_abu_hurayra has external_id="ms-001" and name_ar_normalized set.
        matches = _crossref_match("\u0627\u0628\u0648 \u0647\u0631\u064a\u0631\u0647", candidates)
        assert len(matches) >= 1
        assert all(m.stage == "crossref" for m in matches)

    def test_no_external_id_no_match(self) -> None:
        cand = Candidate(
            bio_id="bio-x",
            name_ar_normalized="\u0639\u0644\u064a",
            external_id=None,
        )
        matches = _crossref_match("\u0639\u0644\u064a", [cand])
        assert matches == []

    def test_empty_mention(self, candidates: list[Candidate]) -> None:
        matches = _crossref_match("", candidates)
        assert matches == []


# ---------------------------------------------------------------------------
# Canonical ID determinism
# ---------------------------------------------------------------------------
class TestCanonicalId:
    def test_deterministic_same_input(self) -> None:
        id1 = _make_canonical_id("\u0627\u0628\u0648 \u0647\u0631\u064a\u0631\u0647")
        id2 = _make_canonical_id("\u0627\u0628\u0648 \u0647\u0631\u064a\u0631\u0647")
        assert id1 == id2

    def test_different_input_different_id(self) -> None:
        id1 = _make_canonical_id("\u0627\u0628\u0648 \u0647\u0631\u064a\u0631\u0647")
        id2 = _make_canonical_id("\u0639\u0644\u064a")
        assert id1 != id2

    def test_is_valid_uuid5(self) -> None:
        cid = _make_canonical_id("test_name")
        parsed = uuid.UUID(cid)
        assert parsed.version == 5

    def test_uses_fixed_namespace(self) -> None:
        expected = str(uuid.uuid5(_CANONICAL_NAMESPACE, "test_input"))
        assert _make_canonical_id("test_input") == expected


# ---------------------------------------------------------------------------
# Blocking index
# ---------------------------------------------------------------------------
class TestBlockingIndex:
    def test_build_index_groups_by_prefix(self, candidates: list[Candidate]) -> None:
        index = _build_blocking_index(candidates)
        # "ابو هريره" starts with "اب", "انس بن مالك" starts with "ان", "علي" starts with "عل"
        assert len(index.blocks_ar) >= 2

    def test_exact_ar_index_populated(self, candidates: list[Candidate]) -> None:
        index = _build_blocking_index(candidates)
        assert "\u0627\u0628\u0648 \u0647\u0631\u064a\u0631\u0647" in index.exact_ar
        assert "\u0627\u0646\u0633 \u0628\u0646 \u0645\u0627\u0644\u0643" in index.exact_ar

    def test_exact_en_index_populated(self, candidates: list[Candidate]) -> None:
        index = _build_blocking_index(candidates)
        assert "abu hurayra" in index.exact_en
        assert "anas ibn malik" in index.exact_en

    def test_crossref_only_has_external_id_candidates(self, candidates: list[Candidate]) -> None:
        index = _build_blocking_index(candidates)
        # Only candidate_abu_hurayra has an external_id
        all_crossref = [c for block in index.crossref_blocks.values() for c in block]
        assert all(c.external_id is not None for c in all_crossref)

    def test_empty_candidates(self) -> None:
        index = _build_blocking_index([])
        assert index.exact_ar == {}
        assert index.exact_en == {}
        assert index.blocks_ar == {}
        assert index.crossref_blocks == {}


# ---------------------------------------------------------------------------
# Indexed exact match
# ---------------------------------------------------------------------------
class TestExactMatchIndexed:
    def test_exact_arabic_match(self, candidates: list[Candidate]) -> None:
        index = _build_blocking_index(candidates)
        matches = _exact_match_indexed("\u0627\u0628\u0648 \u0647\u0631\u064a\u0631\u0647", index)
        assert len(matches) == 1
        assert matches[0].stage == "exact"
        assert matches[0].score == 1.0
        assert matches[0].candidate.bio_id == "bio-001"

    def test_exact_english_match(self, candidates: list[Candidate]) -> None:
        index = _build_blocking_index(candidates)
        matches = _exact_match_indexed("Abu Hurayra", index)
        assert len(matches) == 1
        assert matches[0].candidate.name_en == "Abu Hurayra"

    def test_no_match(self, candidates: list[Candidate]) -> None:
        index = _build_blocking_index(candidates)
        matches = _exact_match_indexed("unknown narrator", index)
        assert matches == []

    def test_empty_mention(self, candidates: list[Candidate]) -> None:
        index = _build_blocking_index(candidates)
        matches = _exact_match_indexed("", index)
        assert matches == []

    def test_parity_with_linear_exact(self, candidates: list[Candidate]) -> None:
        """Indexed exact match produces same results as linear scan."""
        index = _build_blocking_index(candidates)
        name = "\u0627\u0628\u0648 \u0647\u0631\u064a\u0631\u0647"
        linear = _exact_match(name, candidates)
        indexed = _exact_match_indexed(name, index)
        assert len(linear) == len(indexed)
        assert {m.candidate.bio_id for m in linear} == {m.candidate.bio_id for m in indexed}


# ---------------------------------------------------------------------------
# Blocked fuzzy match
# ---------------------------------------------------------------------------
class TestFuzzyMatchBlocked:
    def test_similar_name_matches(self, candidates: list[Candidate]) -> None:
        index = _build_blocking_index(candidates)
        # One-char difference — same prefix block
        matches = _fuzzy_match_blocked("\u0627\u0628\u0648 \u0647\u0631\u064a\u0631\u0629", index)
        assert len(matches) >= 1
        assert all(m.stage == "fuzzy" for m in matches)

    def test_different_prefix_no_match(self, candidates: list[Candidate]) -> None:
        index = _build_blocking_index(candidates)
        # Prefix "xx" has no candidates
        matches = _fuzzy_match_blocked("xx test name", index)
        assert matches == []

    def test_empty_mention(self, candidates: list[Candidate]) -> None:
        index = _build_blocking_index(candidates)
        matches = _fuzzy_match_blocked("", index)
        assert matches == []

    def test_parity_within_block(self, candidates: list[Candidate]) -> None:
        """Blocked fuzzy match finds same results as linear for same-prefix names."""
        index = _build_blocking_index(candidates)
        name = "\u0627\u0628\u0648 \u0647\u0631\u064a\u0631\u0629"
        linear = _fuzzy_match(name, candidates)
        blocked = _fuzzy_match_blocked(name, index)
        # Blocked should find at least everything linear finds within the same block
        linear_same_prefix = [
            m for m in linear if (m.candidate.name_ar_normalized or "")[:2] == name[:2]
        ]
        assert len(blocked) == len(linear_same_prefix)


# ---------------------------------------------------------------------------
# Blocked cross-reference match
# ---------------------------------------------------------------------------
class TestCrossrefMatchBlocked:
    def test_external_id_boosts_match(self, candidates: list[Candidate]) -> None:
        index = _build_blocking_index(candidates)
        matches = _crossref_match_blocked(
            "\u0627\u0628\u0648 \u0647\u0631\u064a\u0631\u0647", index
        )
        assert len(matches) >= 1
        assert all(m.stage == "crossref" for m in matches)

    def test_no_match_different_prefix(self, candidates: list[Candidate]) -> None:
        index = _build_blocking_index(candidates)
        matches = _crossref_match_blocked("xx no match", index)
        assert matches == []

    def test_empty_mention(self, candidates: list[Candidate]) -> None:
        index = _build_blocking_index(candidates)
        matches = _crossref_match_blocked("", index)
        assert matches == []
