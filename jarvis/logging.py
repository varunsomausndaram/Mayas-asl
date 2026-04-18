"""Structured logging setup.

Jarvis uses :mod:`structlog` layered on top of the standard library logger so
that the same records stream to the terminal (human readable) and to the log
file (one JSON object per line). Call :func:`configure_logging` once at
process startup; after that, acquire loggers with :func:`get_logger`.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any

import structlog

_configured = False


def configure_logging(level: str = "INFO", log_dir: Path | None = None) -> None:
    """Install handlers, formatters, and structlog processors.

    Calling this function more than once is a no-op so that importing
    ``jarvis`` from multiple entry points doesn't double-log.
    """
    global _configured
    if _configured:
        return
    _configured = True

    numeric = getattr(logging, level.upper(), logging.INFO)

    # ---------------------------------------------------------- stdlib layer
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(numeric)

    console = logging.StreamHandler(stream=sys.stderr)
    console.setLevel(numeric)
    console.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(console)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "jarvis.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(file_handler)

    # ---------------------------------------------------------- structlog
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if sys.stderr.isatty():
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Return a structlog logger bound to ``name``."""
    return structlog.get_logger(name) if name else structlog.get_logger()
