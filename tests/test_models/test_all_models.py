"""Tests for all Pydantic graph node and edge models.

Covers instantiation, validation, ID prefixes, frozen immutability, and round-trip
serialization for every model in src.models.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.chain import Chain
from src.models.collection import Collection
from src.models.edges import (
    ActiveDuring,
    AppearsIn,
    BasedIn,
    ParallelOf,
    StudiedUnder,
    TransmittedTo,
)
from src.models.enums import (
    ChainClassification,
    Gender,
    HadithGrade,
    HistoricalEventType,
    NarratorGeneration,
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

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _narrator(**overrides: object) -> Narrator:
    defaults: dict[str, object] = {
        "id": "nar:test-001",
        "name_ar": "اسم",
        "name_en": "Name",
        "generation": NarratorGeneration.SAHABI,
        "gender": Gender.MALE,
        "sect_affiliation": SectAffiliation.SUNNI,
        "trustworthiness_consensus": TrustworthinessGrade.THIQA,
    }
    defaults.update(overrides)
    return Narrator(**defaults)  # type: ignore[arg-type]


def _hadith(**overrides: object) -> Hadith:
    defaults: dict[str, object] = {
        "id": "hdt:test-001",
        "matn_ar": "متن الحديث",
        "source_corpus": SourceCorpus.SUNNAH,
    }
    defaults.update(overrides)
    return Hadith(**defaults)  # type: ignore[arg-type]


def _collection(**overrides: object) -> Collection:
    defaults: dict[str, object] = {
        "id": "col:test-001",
        "name_ar": "صحيح البخاري",
        "name_en": "Sahih al-Bukhari",
        "sect": Sect.SUNNI,
    }
    defaults.update(overrides)
    return Collection(**defaults)  # type: ignore[arg-type]


def _chain(**overrides: object) -> Chain:
    defaults: dict[str, object] = {
        "id": "chn:test-001",
        "hadith_id": "hdt:test-001",
        "chain_index": 0,
        "chain_length": 3,
        "is_complete": True,
        "classification": ChainClassification.MUTTASIL,
    }
    defaults.update(overrides)
    return Chain(**defaults)  # type: ignore[arg-type]


def _grading(**overrides: object) -> Grading:
    defaults: dict[str, object] = {
        "id": "grading-001",
        "hadith_id": "hdt:test-001",
        "scholar_name": "Al-Bukhari",
        "grade": HadithGrade.SAHIH,
    }
    defaults.update(overrides)
    return Grading(**defaults)  # type: ignore[arg-type]


def _historical_event(**overrides: object) -> HistoricalEvent:
    defaults: dict[str, object] = {
        "id": "event-001",
        "name_en": "First Fitna",
        "year_start_ah": 35,
        "year_start_ce": 656,
        "event_type": HistoricalEventType.FITNA,
    }
    defaults.update(overrides)
    return HistoricalEvent(**defaults)  # type: ignore[arg-type]


def _location(**overrides: object) -> Location:
    defaults: dict[str, object] = {
        "id": "loc:medina",
        "name_en": "Medina",
    }
    defaults.update(overrides)
    return Location(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Instantiation tests
# ---------------------------------------------------------------------------


class TestInstantiation:
    """Valid instances can be created for every model."""

    def test_narrator(self) -> None:
        n = _narrator()
        assert n.id == "nar:test-001"
        assert n.generation == NarratorGeneration.SAHABI

    def test_hadith(self) -> None:
        h = _hadith()
        assert h.id == "hdt:test-001"
        assert h.source_corpus == SourceCorpus.SUNNAH

    def test_collection(self) -> None:
        c = _collection()
        assert c.id == "col:test-001"
        assert c.sect == Sect.SUNNI

    def test_chain(self) -> None:
        ch = _chain()
        assert ch.id == "chn:test-001"
        assert ch.chain_length == 3

    def test_grading(self) -> None:
        g = _grading()
        assert g.grade == HadithGrade.SAHIH

    def test_historical_event(self) -> None:
        e = _historical_event()
        assert e.event_type == HistoricalEventType.FITNA

    def test_historical_event_via_alias(self) -> None:
        """HistoricalEvent accepts 'type' alias for event_type."""
        e = HistoricalEvent(
            id="event-002",
            name_en="Ridda Wars",
            year_start_ah=11,
            year_start_ce=632,
            type=HistoricalEventType.FITNA,  # type: ignore[call-arg]
        )
        assert e.event_type == HistoricalEventType.FITNA

    def test_location(self) -> None:
        loc = _location()
        assert loc.name_en == "Medina"

    def test_transmitted_to(self) -> None:
        edge = TransmittedTo(
            from_narrator_id="nar:a",
            to_narrator_id="nar:b",
            hadith_id="hdt:001",
            chain_id="chn:001",
            position_in_chain=0,
            transmission_method=TransmissionMethod.HADDATHANA,
        )
        assert edge.transmission_method == TransmissionMethod.HADDATHANA

    def test_appears_in(self) -> None:
        edge = AppearsIn(hadith_id="hdt:001", collection_id="col:001")
        assert edge.hadith_id == "hdt:001"

    def test_parallel_of(self) -> None:
        edge = ParallelOf(
            hadith_id_a="hdt:001",
            hadith_id_b="hdt:002",
            similarity_score=0.95,
            variant_type=VariantType.VERBATIM,
            cross_sect=True,
        )
        assert edge.cross_sect is True

    def test_studied_under(self) -> None:
        edge = StudiedUnder(student_id="nar:a", teacher_id="nar:b")
        assert edge.teacher_id == "nar:b"

    def test_active_during(self) -> None:
        edge = ActiveDuring(narrator_id="nar:a", event_id="event-001")
        assert edge.narrator_id == "nar:a"

    def test_based_in(self) -> None:
        edge = BasedIn(narrator_id="nar:a", location_id="loc:medina")
        assert edge.location_id == "loc:medina"


# ---------------------------------------------------------------------------
# Validation / rejection tests
# ---------------------------------------------------------------------------


class TestValidation:
    """Models reject invalid data with ValidationError."""

    def test_narrator_missing_required_field(self) -> None:
        with pytest.raises(ValidationError):
            Narrator(id="nar:x", name_ar="ا", name_en="A")  # type: ignore[call-arg]

    def test_hadith_missing_matn(self) -> None:
        with pytest.raises(ValidationError):
            Hadith(id="hdt:x")  # type: ignore[call-arg]

    def test_collection_missing_sect(self) -> None:
        with pytest.raises(ValidationError):
            Collection(id="col:x", name_ar="a", name_en="A")  # type: ignore[call-arg]

    def test_chain_missing_chain_length(self) -> None:
        with pytest.raises(ValidationError):
            Chain(  # type: ignore[call-arg]
                id="chn:x",
                hadith_id="hdt:x",
                chain_index=0,
                is_complete=True,
                classification=ChainClassification.MUTTASIL,
            )

    def test_narrator_bad_enum_value(self) -> None:
        with pytest.raises(ValidationError):
            _narrator(gender="nonexistent")

    def test_hadith_bad_source_corpus(self) -> None:
        with pytest.raises(ValidationError):
            _hadith(source_corpus="invalid_corpus")

    def test_grading_bad_grade(self) -> None:
        with pytest.raises(ValidationError):
            _grading(grade="super_sahih")

    def test_transmitted_to_missing_fields(self) -> None:
        with pytest.raises(ValidationError):
            TransmittedTo(from_narrator_id="nar:a")  # type: ignore[call-arg]

    def test_parallel_of_missing_similarity(self) -> None:
        with pytest.raises(ValidationError):
            ParallelOf(  # type: ignore[call-arg]
                hadith_id_a="hdt:001",
                hadith_id_b="hdt:002",
                variant_type=VariantType.VERBATIM,
                cross_sect=True,
            )


# ---------------------------------------------------------------------------
# ID prefix validation (parametrized)
# ---------------------------------------------------------------------------


class TestIdPrefixes:
    """ID prefix validators reject non-conforming IDs."""

    @pytest.mark.parametrize(
        ("model_cls", "prefix", "valid_id"),
        [
            (Narrator, "nar:", "nar:valid-001"),
            (Hadith, "hdt:", "hdt:valid-001"),
            (Collection, "col:", "col:valid-001"),
            (Chain, "chn:", "chn:valid-001"),
        ],
        ids=["narrator", "hadith", "collection", "chain"],
    )
    def test_valid_prefix_accepted(
        self,
        model_cls: type,
        prefix: str,
        valid_id: str,
    ) -> None:
        """Models accept IDs with the correct prefix."""
        factories = {
            Narrator: lambda: _narrator(id=valid_id),
            Hadith: lambda: _hadith(id=valid_id),
            Collection: lambda: _collection(id=valid_id),
            Chain: lambda: _chain(id=valid_id),
        }
        instance = factories[model_cls]()
        assert instance.id == valid_id

    @pytest.mark.parametrize(
        ("model_cls", "bad_id"),
        [
            (Narrator, "bad:narrator-001"),
            (Narrator, "hdt:wrong-prefix"),
            (Hadith, "nar:wrong-001"),
            (Hadith, "hadith-no-prefix"),
            (Collection, "nar:wrong-001"),
            (Collection, ""),
            (Chain, "ch:missing-n"),
            (Chain, "chain:wrong-001"),
        ],
        ids=[
            "narrator-bad-prefix",
            "narrator-hdt-prefix",
            "hadith-nar-prefix",
            "hadith-no-prefix",
            "collection-nar-prefix",
            "collection-empty",
            "chain-short-prefix",
            "chain-long-prefix",
        ],
    )
    def test_invalid_prefix_rejected(self, model_cls: type, bad_id: str) -> None:
        """Models reject IDs with the wrong prefix."""
        factories = {
            Narrator: lambda: _narrator(id=bad_id),
            Hadith: lambda: _hadith(id=bad_id),
            Collection: lambda: _collection(id=bad_id),
            Chain: lambda: _chain(id=bad_id),
        }
        with pytest.raises(ValidationError, match="must start with"):
            factories[model_cls]()


# ---------------------------------------------------------------------------
# Frozen (immutability) tests
# ---------------------------------------------------------------------------


class TestFrozen:
    """All models are frozen (immutable after creation)."""

    def test_narrator_frozen(self) -> None:
        n = _narrator()
        with pytest.raises(ValidationError):
            n.name_en = "Changed"  # type: ignore[misc]

    def test_hadith_frozen(self) -> None:
        h = _hadith()
        with pytest.raises(ValidationError):
            h.matn_ar = "Changed"  # type: ignore[misc]

    def test_collection_frozen(self) -> None:
        c = _collection()
        with pytest.raises(ValidationError):
            c.name_en = "Changed"  # type: ignore[misc]

    def test_chain_frozen(self) -> None:
        ch = _chain()
        with pytest.raises(ValidationError):
            ch.chain_length = 99  # type: ignore[misc]

    def test_grading_frozen(self) -> None:
        g = _grading()
        with pytest.raises(ValidationError):
            g.scholar_name = "Changed"  # type: ignore[misc]

    def test_historical_event_frozen(self) -> None:
        e = _historical_event()
        with pytest.raises(ValidationError):
            e.name_en = "Changed"  # type: ignore[misc]

    def test_location_frozen(self) -> None:
        loc = _location()
        with pytest.raises(ValidationError):
            loc.name_en = "Changed"  # type: ignore[misc]

    def test_transmitted_to_frozen(self) -> None:
        edge = TransmittedTo(
            from_narrator_id="nar:a",
            to_narrator_id="nar:b",
            hadith_id="hdt:001",
            chain_id="chn:001",
            position_in_chain=0,
            transmission_method=TransmissionMethod.AN,
        )
        with pytest.raises(ValidationError):
            edge.position_in_chain = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Round-trip (model_dump -> reconstruct) tests
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """model_dump() output can reconstruct an identical instance."""

    def test_narrator_round_trip(self) -> None:
        original = _narrator(aliases=["Alias1", "Alias2"], kunya="Abu Test")
        data = original.model_dump()
        rebuilt = Narrator(**data)
        assert rebuilt == original

    def test_hadith_round_trip(self) -> None:
        original = _hadith(
            matn_en="Deeds are by intentions",
            topic_tags=["faith", "intention"],
        )
        data = original.model_dump()
        rebuilt = Hadith(**data)
        assert rebuilt == original

    def test_collection_round_trip(self) -> None:
        original = _collection(canonical_rank=1, total_hadiths=7563)
        data = original.model_dump()
        rebuilt = Collection(**data)
        assert rebuilt == original

    def test_chain_round_trip(self) -> None:
        original = _chain(narrator_ids=["nar:a", "nar:b", "nar:c"])
        data = original.model_dump()
        rebuilt = Chain(**data)
        assert rebuilt == original

    def test_grading_round_trip(self) -> None:
        original = _grading(methodology_school="Hanbali", era="classical")
        data = original.model_dump()
        rebuilt = Grading(**data)
        assert rebuilt == original

    def test_historical_event_round_trip(self) -> None:
        original = _historical_event(description="A major civil war")
        data = original.model_dump()
        rebuilt = HistoricalEvent(**data)
        assert rebuilt == original

    def test_location_round_trip(self) -> None:
        original = _location(
            name_ar="المدينة",
            lat=24.4672,
            lon=39.6112,
            political_entity_period={"622-661": "Rashidun"},
        )
        data = original.model_dump()
        rebuilt = Location(**data)
        assert rebuilt == original

    def test_transmitted_to_round_trip(self) -> None:
        original = TransmittedTo(
            from_narrator_id="nar:a",
            to_narrator_id="nar:b",
            hadith_id="hdt:001",
            chain_id="chn:001",
            position_in_chain=0,
            transmission_method=TransmissionMethod.HADDATHANA,
        )
        data = original.model_dump()
        rebuilt = TransmittedTo(**data)
        assert rebuilt == original

    def test_parallel_of_round_trip(self) -> None:
        original = ParallelOf(
            hadith_id_a="hdt:001",
            hadith_id_b="hdt:002",
            similarity_score=0.88,
            variant_type=VariantType.CLOSE_PARAPHRASE,
            cross_sect=False,
        )
        data = original.model_dump()
        rebuilt = ParallelOf(**data)
        assert rebuilt == original

    def test_studied_under_round_trip(self) -> None:
        original = StudiedUnder(
            student_id="nar:a",
            teacher_id="nar:b",
            period_ah="100-120",
            location_id="loc:medina",
            source="Tahdhib al-Tahdhib",
        )
        data = original.model_dump()
        rebuilt = StudiedUnder(**data)
        assert rebuilt == original

    def test_active_during_round_trip(self) -> None:
        original = ActiveDuring(
            narrator_id="nar:a",
            event_id="event-001",
            role="participant",
            affiliation="Umayyad",
        )
        data = original.model_dump()
        rebuilt = ActiveDuring(**data)
        assert rebuilt == original

    def test_based_in_round_trip(self) -> None:
        original = BasedIn(
            narrator_id="nar:a",
            location_id="loc:kufa",
            period_ah="60-80",
            role="teacher",
        )
        data = original.model_dump()
        rebuilt = BasedIn(**data)
        assert rebuilt == original


# ---------------------------------------------------------------------------
# Optional field defaults
# ---------------------------------------------------------------------------


class TestDefaults:
    """Optional fields have the expected default values."""

    def test_narrator_optional_defaults(self) -> None:
        n = _narrator()
        assert n.kunya is None
        assert n.nisba is None
        assert n.laqab is None
        assert n.birth_year_ah is None
        assert n.death_year_ah is None
        assert n.aliases == []
        assert n.betweenness_centrality is None
        assert n.pagerank is None

    def test_hadith_optional_defaults(self) -> None:
        h = _hadith()
        assert h.matn_en is None
        assert h.isnad_raw_ar is None
        assert h.topic_tags == []
        assert h.has_shia_parallel is False
        assert h.has_sunni_parallel is False

    def test_chain_optional_defaults(self) -> None:
        ch = _chain()
        assert ch.full_chain_text_ar is None
        assert ch.is_elevated is False
        assert ch.narrator_ids == []
