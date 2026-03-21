"""
Structured logging configuration for RadardeOfertas.

Supports two output formats controlled by the ``LOG_FORMAT`` env var:
* ``text`` (default) – human-readable with colours, matches existing style
* ``json``           – structured JSON lines suitable for log aggregators

Log level is controlled by ``LOG_LEVEL`` (default ``INFO``).

Usage
-----
Call :func:`configure_logging` once at process start (main.py, celery_app, etc.)::

    from services.logging_config import configure_logging
    configure_logging()
"""
from __future__ import annotations

import logging
import os
import sys


def configure_logging() -> None:
    """Configure root logger according to ``LOG_FORMAT`` and ``LOG_LEVEL``."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = os.getenv("LOG_FORMAT", "text").lower()

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any existing handlers (avoid duplicate messages on re-configure)
    root.handlers.clear()

    if fmt == "json":
        handler = _build_json_handler(level)
    else:
        handler = _build_text_handler(level)

    root.addHandler(handler)


# ── formatters ────────────────────────────────────────────────────────────────


def _build_text_handler(level: int) -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(fmt)
    return handler


def _build_json_handler(level: int) -> logging.StreamHandler:
    try:
        try:
            from pythonjsonlogger.json import JsonFormatter  # type: ignore[import]
        except ImportError:
            from pythonjsonlogger.jsonlogger import JsonFormatter  # type: ignore[import]

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        fmt = JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        handler.setFormatter(fmt)
        return handler
    except ImportError:
        # Fallback to text if python-json-logger is not installed
        logging.warning(
            "python-json-logger not available; falling back to text logging"
        )
        return _build_text_handler(level)
