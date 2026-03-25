"""Structured JSON logging via structlog.

Centralised logging configuration for the isnad-graph platform.

Standard log fields
-------------------
- ``timestamp`` — ISO-8601 UTC timestamp
- ``level`` — log level (info, warning, error, ...)
- ``service`` — service name (``isnad-graph``)
- ``logger_name`` — Python module / logger name
- ``message`` — human-readable event description
- ``request_id`` — (API requests only) unique per-request trace ID

Configuration
-------------
``LOG_LEVEL``  — environment variable controlling verbosity (default ``INFO``)
``LOG_FORMAT`` — ``json`` for structured JSON output, ``console`` for human-readable
"""

from __future__ import annotations

import logging
import os

import structlog

SERVICE_NAME = "isnad-graph"

__all__ = ["SERVICE_NAME", "configure_logging", "get_logger"]


def _add_service_name(
    logger: object,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Inject the ``service`` field into every log event."""
    event_dict.setdefault("service", SERVICE_NAME)
    return event_dict


def configure_logging() -> None:
    """Configure structlog once. Call at application startup.

    Reads ``LOG_LEVEL`` and ``LOG_FORMAT`` from :func:`src.config.get_settings`
    when available, falling back to environment variables / defaults when settings
    cannot be loaded (e.g. during early import or in test environments).

    When ``LOG_FORMAT`` is ``json`` the output is newline-delimited JSON suitable
    for log aggregation systems (ELK, Datadog, CloudWatch, etc.).
    """
    try:
        from src.config import get_settings

        settings = get_settings()
        log_level = settings.log_level.upper()
        log_format = settings.log_format
    except Exception:  # noqa: BLE001
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        log_format = os.environ.get("LOG_FORMAT", "console")

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        _add_service_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    renderer: structlog.types.Processor
    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level, logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named logger bound with ``logger_name``."""
    return structlog.get_logger(logger_name=name)  # type: ignore[no-any-return]


configure_logging()
