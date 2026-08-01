"""Structured logging setup for jobhunt_core (design.md §9).

Phase-1 scope (phases.md Phase 1, tasks.md T1.5): wire a stderr
handler (human-readable) and a rotating JSON-lines file handler under
a caller-supplied log directory. The per-agent-run structured event
(``RunEvent`` / ``log_run_event``, api.md §8) is added once
``schemas/`` exists (Phase 4) — this module only owns the handler
plumbing, not the event schema.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
from pathlib import Path
from typing import Any

_LOGGER_NAME = "jobhunt"
_CONFIGURED_ATTR = "_jobhunt_configured"
_MAX_BYTES = 5_000_000
_BACKUP_COUNT = 3


class _JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON for the file handler."""

    def format(self, record: logging.LogRecord) -> str:
        """Render ``record`` as a single JSON line.

        Args:
            record: The log record to format.

        Returns:
            A JSON-encoded string with no embedded newlines.
        """
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(log_dir: Path, level: str = "INFO") -> logging.Logger:
    """Configure the shared ``jobhunt`` logger.

    Idempotent: calling this more than once does not attach duplicate
    handlers (tasks.md T1.5 completion checklist).

    Never logs secrets or full LLM prompt/response bodies at this
    layer — that gating happens where those bodies originate
    (design.md §9, rules.md §Logging Rules), not here.

    Args:
        log_dir: Directory the rotating log file is written under.
            Created if it does not already exist.
        level: Log level name for the ``jobhunt`` logger, e.g. "INFO"
            or "DEBUG".

    Returns:
        The configured ``jobhunt`` logger.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    if getattr(logger, _CONFIGURED_ATTR, False):
        return logger

    logger.setLevel(level)
    logger.propagate = False

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(stream_handler)

    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "jobhunt.log", maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT
    )
    file_handler.setFormatter(_JsonFormatter())
    logger.addHandler(file_handler)

    setattr(logger, _CONFIGURED_ATTR, True)
    return logger
