"""Shared pytest fixtures."""

import logging
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _reset_jobhunt_logger() -> Iterator[None]:
    """Reset the shared ``jobhunt`` logger before and after each test.

    ``configure_logging()`` is intentionally idempotent within one
    process/run (design.md §9, tasks.md T1.5) — that's correct for
    production, but it means the module-level logger otherwise leaks
    handlers and its "configured" marker across tests. Reset both here
    so each test observes a clean logger, regardless of test order.
    """

    def _reset() -> None:
        logger = logging.getLogger("jobhunt")
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
        if hasattr(logger, "_jobhunt_configured"):
            delattr(logger, "_jobhunt_configured")

    _reset()
    yield
    _reset()
