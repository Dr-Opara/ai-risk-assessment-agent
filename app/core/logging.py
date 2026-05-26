"""
Structured logging configuration using structlog.

Why structlog?
- Emits JSON logs in production (great for Datadog/CloudWatch/ELK).
- Emits pretty colored logs locally for developer ergonomics.
- Adds context (request IDs, user IDs) cleanly.
"""
import logging
import sys
from typing import Any

import structlog


def configure_logging(
    log_level: str = "INFO",
    json_logs: bool = False,
) -> None:
    """
    Configure structlog + stdlib logging once at application startup.

    Args:
        log_level: Standard log level name (DEBUG, INFO, WARNING, ERROR).
        json_logs: If True, emit JSON. If False, emit colored console output.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Base stdlib logging — structlog will piggyback on this.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    # Silence overly chatty libraries
    for noisy in ("uvicorn.access", "httpx", "httpcore", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Convenience accessor — use this everywhere instead of stdlib logging."""
    return structlog.get_logger(name)