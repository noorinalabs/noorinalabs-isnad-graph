"""Tests for the data quality validation framework."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.parse.schemas import COLLECTION_SCHEMA, HADITH_SCHEMA, NARRATOR_MENTION_SCHEMA
from src.parse.validate import (
    CheckStatus,
    DriftResult,
    FileReport,
    Strictness,
    ValidationReport,
    validate_staging,
)


@pytest.fixture
def staging_dir(tmp_path: Path) -> Path:
    """Create a temporary staging directory."""
    return tmp_path


def _write_hadith_parquet(path: Path, rows: list[dict]) -> None:
    """Write a hadith Parquet file with the correct schema."""
    arrays = {}
    for field in HADITH_SCHEMA:
        values = [r.get(field.name) for r in rows]
        arrays[field.name] = pa.array(values, type=field.type)
    table = pa.table(arrays, schema=HADITH_SCHEMA)
    pq.write_table(table, path)


def _write_collection_parquet(path: Path, rows: list[dict]) -> None:
    """Write a collection Parquet file."""
    arrays = {}
    for field in COLLECTION_SCHEMA:
        values = [r.get(field.name) for r in rows]
        arrays[field.name] = pa.array(values, type=field.type)
    table = pa.table(arrays, schema=COLLECTION_SCHEMA)
    pq.write_table(table, path)


def _write_narrator_mention_parquet(path: Path, rows: list[dict]) -> None:
    """Write a narrator mentions Parquet file."""
    arrays = {}
    for field in NARRATOR_MENTION_SCHEMA:
        values = [r.get(field.name) for r in rows]
        arrays[field.name] = pa.array(values, type=field.type)
    table = pa.table(arrays, schema=NARRATOR_MENTION_SCHEMA)
    pq.write_table(table, path)


def _make_hadith_row(
    source_id: str = "h1",
    source_corpus: str = "test",
    collection_name: str = "bukhari",
    sect: str = "sunni",
    matn_ar: str | None = "\u0628\u0633\u0645 \u0627\u0644\u0644\u0647",
    matn_en: str | None = "In the name of God",
    **kwargs,
) -> dict:
    return {
        "source_id": source_id,
        "source_corpus": source_corpus,
        "collection_name": collection_name,
        "book_number": kwargs.get("book_number", 1),
        "chapter_number": kwargs.get("chapter_number", 1),
        "hadith_number": kwargs.get("hadith_number", 1),
        "matn_ar": matn_ar,
        "matn_en": matn_en,
        "isnad_raw_ar": kwargs.get("isnad_raw_ar"),
        "isnad_raw_en": kwargs.get("isnad_raw_en"),
        "full_text_ar": kwargs.get("full_text_ar"),
        "full_text_en": kwargs.get("full_text_en"),
        "grade": kwargs.get("grade"),
        "chapter_name_ar": kwargs.get("chapter_name_ar"),
        "chapter_name_en": kwargs.get("chapter_name_en"),
        "sect": sect,
    }


class TestValidationReportModels:
    """Test Pydantic report model structure."""

    def test_check_result_frozen(self):
        from src.parse.validate import CheckResult

        cr = CheckResult(name="test", status=CheckStatus.PASS, message="ok")
        with pytest.raises(Exception):
            cr.name = "changed"  # type: ignore[misc]

    def test_file_report_frozen(self):
        fr = FileReport(
            file="test.parquet",
            source="test",
            rows=0,
            columns=0,
            null_percentages={},
            checks=[],
            drift=[],
            passed=True,
        )
        with pytest.raises(Exception):
            fr.passed = False  # type: ignore[misc]

    def test_validation_report_serialization(self):
        report = ValidationReport(
            timestamp="2026-01-01T00:00:00Z",
            staging_dir="/tmp/test",
            strictness=Strictness.WARN,
            total_files=0,
            total_rows=0,
            files=[],
            passed=True,
        )
        data = report.model_dump(mode="json")
        assert data["strictness"] == "warn"
        assert data["passed"] is True

    def test_drift_result_model(self):
        dr = DriftResult(
            metric="row_count",
            baseline_value=100,
            current_value=80,
            drift_pct=20.0,
            within_tolerance=True,
            tolerance_pct=30.0,
        )
        assert dr.within_tolerance is True
        assert dr.drift_pct == 20.0


class TestValidateStaging:
    """Test the main validate_staging function."""

    def test_empty_directory(self, staging_dir: Path):
        report = validate_staging(staging_dir)
        assert report.total_files == 0
        assert report.passed is True

    def test_valid_hadith_file(self, staging_dir: Path):
        rows = [_make_hadith_row(source_id=f"h{i}") for i in range(5)]
        _write_hadith_parquet(staging_dir / "hadiths_test_source.parquet", rows)

        report = validate_staging(staging_dir)
        assert report.total_files == 1
        assert report.total_rows == 5
        assert report.files[0].passed is True
        assert report.files[0].source == "test_source"

    def test_schema_conformance_pass(self, staging_dir: Path):
        rows = [_make_hadith_row(source_id=f"h{i}") for i in range(3)]
        _write_hadith_parquet(staging_dir / "hadiths_test.parquet", rows)

        report = validate_staging(staging_dir)
        schema_checks = [c for c in report.files[0].checks if c.name == "schema_conformance"]
        assert len(schema_checks) == 1
        assert schema_checks[0].status == CheckStatus.PASS

    def test_duplicate_detection(self, staging_dir: Path):
        rows = [
            _make_hadith_row(source_id="h1"),
            _make_hadith_row(source_id="h1"),
            _make_hadith_row(source_id="h2"),
        ]
        _write_hadith_parquet(staging_dir / "hadiths_test.parquet", rows)

        report = validate_staging(staging_dir)
        dupe_checks = [c for c in report.files[0].checks if c.name == "duplicate_ids"]
        assert len(dupe_checks) == 1
        assert dupe_checks[0].value == 1
        assert dupe_checks[0].status == CheckStatus.WARN

    def test_arabic_encoding_check(self, staging_dir: Path):
        rows = [
            _make_hadith_row(source_id="h1", matn_ar="\u0628\u0633\u0645"),
            _make_hadith_row(source_id="h2", matn_ar="\u0627\u0644\u0644\u0647"),
            _make_hadith_row(source_id="h3", matn_ar="no arabic here"),
        ]
        _write_hadith_parquet(staging_dir / "hadiths_test.parquet", rows)

        report = validate_staging(staging_dir)
        ar_checks = [c for c in report.files[0].checks if c.name == "arabic_encoding_matn_ar"]
        assert len(ar_checks) == 1
        assert ar_checks[0].value == pytest.approx(66.67, abs=0.01)

    def test_null_check_required_columns(self, staging_dir: Path):
        rows = [_make_hadith_row(source_id=f"h{i}") for i in range(3)]
        _write_hadith_parquet(staging_dir / "hadiths_test.parquet", rows)

        report = validate_staging(staging_dir)
        null_checks = [c for c in report.files[0].checks if c.name.startswith("null_check_")]
        assert len(null_checks) > 0
        for nc in null_checks:
            assert nc.status == CheckStatus.PASS

    def test_empty_matn_checks(self, staging_dir: Path):
        rows = [
            _make_hadith_row(source_id="h1", matn_ar=None, matn_en=None),
            _make_hadith_row(source_id="h2", matn_ar="", matn_en="  "),
            _make_hadith_row(source_id="h3"),
        ]
        _write_hadith_parquet(staging_dir / "hadiths_test.parquet", rows)

        report = validate_staging(staging_dir)
        empty_ar = [c for c in report.files[0].checks if c.name == "empty_matn_ar"]
        assert len(empty_ar) == 1
        assert empty_ar[0].value == 2  # 1 null + 1 empty string

    def test_collection_file(self, staging_dir: Path):
        rows = [
            {
                "collection_id": "c1",
                "name_ar": "\u0635\u062d\u064a\u062d",
                "name_en": "Sahih Bukhari",
                "compiler_name": "Bukhari",
                "compilation_year_ah": 256,
                "sect": "sunni",
                "total_hadiths": 7563,
                "source_corpus": "test",
            }
        ]
        _write_collection_parquet(staging_dir / "collections_test.parquet", rows)

        report = validate_staging(staging_dir)
        assert report.total_files == 1
        assert report.files[0].passed is True
        assert report.files[0].source == "test"


class TestStrictnessLevels:
    """Test strict vs warn mode behavior."""

    def test_warn_mode_passes_with_warnings(self, staging_dir: Path):
        rows = [
            _make_hadith_row(source_id="h1"),
            _make_hadith_row(source_id="h1"),  # duplicate
        ]
        _write_hadith_parquet(staging_dir / "hadiths_test.parquet", rows)

        report = validate_staging(staging_dir, strictness=Strictness.WARN)
        assert report.passed is True
        assert report.strictness == Strictness.WARN

    def test_strict_mode_fails_on_schema_mismatch(self, staging_dir: Path):
        # Write a file with wrong schema (missing required columns)
        table = pa.table({"wrong_col": pa.array(["a", "b"])})
        pq.write_table(table, staging_dir / "hadiths_test.parquet")

        report = validate_staging(staging_dir, strictness=Strictness.STRICT)
        assert report.passed is False


class TestDriftDetection:
    """Test drift detection against baselines."""

    def test_drift_within_tolerance(self, staging_dir: Path):
        rows = [_make_hadith_row(source_id=f"h{i}") for i in range(90)]
        _write_hadith_parquet(staging_dir / "hadiths_test.parquet", rows)

        baselines = {"hadiths_test": {"row_count": 100}}
        report = validate_staging(staging_dir, baselines=baselines, drift_tolerance_pct=20.0)
        assert len(report.files[0].drift) == 1
        assert report.files[0].drift[0].within_tolerance is True
        assert report.files[0].drift[0].drift_pct == 10.0

    def test_drift_exceeds_tolerance(self, staging_dir: Path):
        rows = [_make_hadith_row(source_id=f"h{i}") for i in range(50)]
        _write_hadith_parquet(staging_dir / "hadiths_test.parquet", rows)

        baselines = {"hadiths_test": {"row_count": 100}}
        report = validate_staging(
            staging_dir,
            baselines=baselines,
            drift_tolerance_pct=10.0,
            strictness=Strictness.STRICT,
        )
        assert len(report.files[0].drift) == 1
        assert report.files[0].drift[0].within_tolerance is False
        assert report.files[0].drift[0].drift_pct == 50.0
        assert report.passed is False

    def test_drift_warn_mode_doesnt_fail(self, staging_dir: Path):
        rows = [_make_hadith_row(source_id=f"h{i}") for i in range(10)]
        _write_hadith_parquet(staging_dir / "hadiths_test.parquet", rows)

        baselines = {"hadiths_test": {"row_count": 100}}
        report = validate_staging(
            staging_dir,
            baselines=baselines,
            drift_tolerance_pct=5.0,
            strictness=Strictness.WARN,
        )
        # Drift exceeds tolerance but warn mode doesn't fail on drift
        assert report.files[0].drift[0].within_tolerance is False
        assert report.passed is True

    def test_no_baseline_no_drift(self, staging_dir: Path):
        rows = [_make_hadith_row(source_id=f"h{i}") for i in range(5)]
        _write_hadith_parquet(staging_dir / "hadiths_test.parquet", rows)

        report = validate_staging(staging_dir, baselines={})
        assert len(report.files[0].drift) == 0


class TestJSONOutput:
    """Test JSON report generation."""

    def test_json_report_written(self, staging_dir: Path, tmp_path: Path):
        rows = [_make_hadith_row(source_id=f"h{i}") for i in range(3)]
        _write_hadith_parquet(staging_dir / "hadiths_test.parquet", rows)

        json_path = tmp_path / "reports" / "report.json"
        validate_staging(staging_dir, output_json=json_path)

        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data["total_files"] == 1
        assert data["total_rows"] == 3
        assert data["passed"] is True
        assert len(data["files"]) == 1
        assert data["files"][0]["source"] == "test"

    def test_json_roundtrip(self, staging_dir: Path, tmp_path: Path):
        rows = [_make_hadith_row(source_id=f"h{i}") for i in range(3)]
        _write_hadith_parquet(staging_dir / "hadiths_test.parquet", rows)

        json_path = tmp_path / "report.json"
        report = validate_staging(staging_dir, output_json=json_path)

        data = json.loads(json_path.read_text())
        roundtrip = ValidationReport(**data)
        assert roundtrip.total_files == report.total_files
        assert roundtrip.passed == report.passed


class TestMultipleFileTypes:
    """Test validation across different file types."""

    def test_mixed_file_types(self, staging_dir: Path):
        hadith_rows = [_make_hadith_row(source_id=f"h{i}") for i in range(5)]
        _write_hadith_parquet(staging_dir / "hadiths_test.parquet", hadith_rows)

        collection_rows = [
            {
                "collection_id": "c1",
                "name_ar": None,
                "name_en": "Test Collection",
                "compiler_name": None,
                "compilation_year_ah": None,
                "sect": "sunni",
                "total_hadiths": None,
                "source_corpus": "test",
            }
        ]
        _write_collection_parquet(staging_dir / "collections_test.parquet", collection_rows)

        report = validate_staging(staging_dir)
        assert report.total_files == 2
        assert report.total_rows == 6

    def test_narrator_mentions(self, staging_dir: Path):
        rows = [
            {
                "mention_id": "m1",
                "source_hadith_id": "h1",
                "source_corpus": "test",
                "position_in_chain": 1,
                "name_ar": "\u0639\u0644\u064a",
                "name_en": "Ali",
                "name_ar_normalized": None,
                "transmission_method": None,
            }
        ]
        _write_narrator_mention_parquet(staging_dir / "narrator_mentions_test.parquet", rows)

        report = validate_staging(staging_dir)
        assert report.total_files == 1
        assert report.files[0].passed is True
