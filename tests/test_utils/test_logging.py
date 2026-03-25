"""Tests for structured logging configuration."""

from __future__ import annotations

import json

import pytest
import structlog

from src.utils.logging import SERVICE_NAME, _add_service_name, configure_logging, get_logger


class TestConfigureLogging:
    """Verify structlog configuration for JSON and console modes."""

    def test_get_logger_returns_bound_logger(self) -> None:
        logger = get_logger("test.module")
        assert logger is not None

    def test_service_name_constant(self) -> None:
        assert SERVICE_NAME == "isnad-graph"

    def test_json_output_contains_standard_fields(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When LOG_FORMAT=json, output must be valid JSON with standard fields."""
        monkeypatch.setenv("LOG_FORMAT", "json")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        structlog.reset_defaults()
        configure_logging()

        logger = get_logger("test.json_output")
        logger.info("test_event", extra_field="value")

        captured = capsys.readouterr()
        # The log line should be valid JSON
        line = captured.out.strip().splitlines()[-1]
        parsed = json.loads(line)
        assert parsed["event"] == "test_event"
        assert parsed["level"] == "info"
        assert parsed["service"] == "isnad-graph"
        assert "timestamp" in parsed
        assert parsed["extra_field"] == "value"
        assert parsed["logger_name"] == "test.json_output"

        # Cleanup: restore console mode
        monkeypatch.setenv("LOG_FORMAT", "console")
        structlog.reset_defaults()
        configure_logging()

    def test_json_renderer_produces_valid_json(self) -> None:
        """Directly test that the JSON processor chain produces valid JSON."""
        processors: list[structlog.types.Processor] = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            _add_service_name,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ]

        event_dict: dict[str, object] = {"event": "test_event", "extra": "data"}
        for proc in processors:
            event_dict = proc(None, "info", event_dict)  # type: ignore[assignment]

        assert isinstance(event_dict, str)
        parsed = json.loads(event_dict)  # type: ignore[arg-type]
        assert parsed["event"] == "test_event"
        assert parsed["level"] == "info"
        assert parsed["service"] == "isnad-graph"
        assert "timestamp" in parsed
        assert parsed["extra"] == "data"

    def test_add_service_name_processor(self) -> None:
        """The _add_service_name processor injects service field."""
        event_dict: dict[str, object] = {"event": "test"}
        result = _add_service_name(None, "info", event_dict)
        assert result["service"] == "isnad-graph"

    def test_add_service_name_does_not_override(self) -> None:
        """If service is already set, _add_service_name preserves it."""
        event_dict: dict[str, object] = {"event": "test", "service": "custom"}
        result = _add_service_name(None, "info", event_dict)
        assert result["service"] == "custom"

    def test_log_level_configurable(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Setting LOG_LEVEL=WARNING should suppress INFO messages."""
        monkeypatch.setenv("LOG_FORMAT", "json")
        monkeypatch.setenv("LOG_LEVEL", "WARNING")

        structlog.reset_defaults()
        configure_logging()

        logger = get_logger("test.level")
        logger.info("should_not_appear")
        logger.warning("should_appear")

        captured = capsys.readouterr()
        lines = [line for line in captured.out.strip().splitlines() if line.strip()]
        # Only the warning should have been emitted
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["event"] == "should_appear"
        assert parsed["level"] == "warning"

        # Cleanup
        monkeypatch.setenv("LOG_FORMAT", "console")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        structlog.reset_defaults()
        configure_logging()
