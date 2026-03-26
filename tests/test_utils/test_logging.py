"""Tests for structured logging configuration."""

from __future__ import annotations

import io
import json
import logging

import structlog

from src.utils.logging import SERVICE_NAME, _add_service_name, configure_logging, get_logger


def _make_json_logger(buf: io.StringIO, level: int = logging.DEBUG) -> structlog.stdlib.BoundLogger:
    """Configure structlog to write JSON into *buf* and return a fresh logger.

    Bypasses ``cache_logger_on_first_use`` so tests get the exact
    configuration they request, regardless of what the module-level
    ``configure_logging()`` call cached at import time.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            _add_service_name,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=buf),
        cache_logger_on_first_use=False,
    )
    return structlog.get_logger()  # type: ignore[no-any-return]


class TestConfigureLogging:
    """Verify structlog configuration for JSON and console modes."""

    def test_get_logger_returns_bound_logger(self) -> None:
        logger = get_logger("test.module")
        assert logger is not None

    def test_service_name_constant(self) -> None:
        assert SERVICE_NAME == "isnad-graph"

    def test_json_output_contains_standard_fields(self) -> None:
        """When configured for JSON, output must be valid JSON with standard fields."""
        buf = io.StringIO()
        logger = _make_json_logger(buf).bind(logger_name="test.json_output")
        logger.info("test_event", extra_field="value")

        lines = [ln for ln in buf.getvalue().strip().splitlines() if ln.strip()]
        assert lines, f"No log output captured. buf={buf.getvalue()!r}"
        parsed = json.loads(lines[-1])
        assert parsed["event"] == "test_event"
        assert parsed["level"] == "info"
        assert parsed["service"] == "isnad-graph"
        assert "timestamp" in parsed
        assert parsed["extra_field"] == "value"
        assert parsed["logger_name"] == "test.json_output"

        # Cleanup: restore defaults
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
        parsed = json.loads(event_dict)
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

    def test_log_level_configurable(self) -> None:
        """Setting level to WARNING should suppress INFO messages."""
        buf = io.StringIO()
        logger = _make_json_logger(buf, level=logging.WARNING).bind(logger_name="test.level")
        logger.info("should_not_appear")
        logger.warning("should_appear")

        lines = [ln for ln in buf.getvalue().strip().splitlines() if ln.strip()]
        # Only the warning should have been emitted
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["event"] == "should_appear"
        assert parsed["level"] == "warning"

        # Cleanup
        structlog.reset_defaults()
        configure_logging()
