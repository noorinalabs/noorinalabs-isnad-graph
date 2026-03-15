"""Structured logging via structlog. Configured once at import time."""

from __future__ import annotations

import logging

import structlog

from src.config import get_settings

__all__ = ["configure_logging", "get_logger"]


def configure_logging() -> None:
    """Configure structlog once. Call at application startup."""
    settings = get_settings()
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    renderer: structlog.types.Processor
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named logger bound with ``logger_name``."""
    return structlog.get_logger(logger_name=name)  # type: ignore[no-any-return]


configure_logging()
