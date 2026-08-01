"""Tests for jobhunt_core.logging_config (tasks.md T1.5 completion checklist)."""

import logging
from pathlib import Path

from jobhunt_core.logging_config import configure_logging


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    """Calling configure_logging twice does not attach duplicate handlers."""
    logger = configure_logging(tmp_path)
    handler_count = len(logger.handlers)

    configure_logging(tmp_path)

    assert len(logger.handlers) == handler_count


def test_configure_logging_creates_rotating_log_file(tmp_path: Path) -> None:
    """A log call after configuration writes to <log_dir>/jobhunt.log."""
    configure_logging(tmp_path)
    logging.getLogger("jobhunt").info("test message")

    assert (tmp_path / "jobhunt.log").exists()
