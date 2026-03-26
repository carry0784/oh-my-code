"""
Operational Logging — K-Dexter Trading System

Structured logging via structlog → stdlib logging.
Output destinations:
  - StreamHandler(stdout): always active (STREAM_ONLY baseline)
  - RotatingFileHandler: active when log_file_path is set (FILE_PERSISTED)

Handler duplication prevention: setup_logging() clears existing handlers
on the root logger before attaching new ones, making it safe to call
multiple times (tests, reloads).
"""
import logging
import sys
from logging.handlers import RotatingFileHandler

import structlog
from app.core.config import settings

# Module-level log mode — set during setup_logging(), readable externally
log_mode: str = "UNKNOWN"


def setup_logging() -> None:
    """Configure structlog + stdlib logging pipeline.

    structlog renders structured events and delegates to stdlib logging.
    stdlib root logger has StreamHandler (always) + RotatingFileHandler (optional).
    Both handlers receive identical structured output.

    Safe to call multiple times — existing root handlers are cleared first.
    """
    global log_mode

    # ── Determine log level ──
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # ── Configure stdlib root logger (clear existing handlers first) ──
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    # Formatter passes through pre-rendered structlog output
    formatter = logging.Formatter("%(message)s")

    # Handler 1: stdout (always)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)
    root.addHandler(stream_handler)

    # Handler 2: rotating file (optional, when log_file_path is set)
    if settings.log_file_path:
        file_handler = RotatingFileHandler(
            settings.log_file_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root.addHandler(file_handler)
        log_mode = "FILE_PERSISTED"
    else:
        log_mode = "STREAM_ONLY"

    # ── Configure structlog → stdlib logging ──
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.debug:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            renderer,
            # Final step: send rendered string to stdlib logging
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,  # allow reconfiguration in tests
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
