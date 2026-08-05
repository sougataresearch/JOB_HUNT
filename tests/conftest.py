"""Shared pytest fixtures.

``FakeLLMProvider`` lives here (not a separate ``tests/support/``
module) deliberately: pytest test directories under this project have
no ``__init__.py`` files, so cross-directory absolute imports like
``from tests.support.fake_llm import ...`` are fragile (they'd require
adding ``__init__.py`` throughout ``tests/``, changing how pytest's
default import mode collects every existing test file). A fixture
defined in the top-level ``conftest.py`` is auto-discovered by pytest
in any subdirectory with no import-path concerns -- the standard,
idiomatic way to share test utilities across directories.
"""

import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import ClassVar, TypeVar

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from jobhunt_core.llm.types import LLMResponse, StructuredLLMResponse
from jobhunt_core.storage.db import create_session_factory, create_sqlite_engine
from jobhunt_core.storage.models import Base

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class FakeLLMProvider:
    """An ``LLMProvider`` that returns a fixed, pre-scripted structured response.

    No live LLM calls (testing.md). Validates an agent's own assembly
    logic (prompt rendering, response merging) deterministically --
    does NOT validate real extraction quality, which needs a live
    model call (flagged wherever this fake is used).
    """

    name: ClassVar[str] = "fake"

    def __init__(self, structured_response: BaseModel) -> None:
        """Store the response every ``complete_structured`` call will return."""
        self._structured_response = structured_response
        self.last_prompt: str | None = None

    def complete(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Return a fixed, minimal free-text response (unused by this agent)."""
        self.last_prompt = prompt
        return LLMResponse(
            text="fake", tokens_in=1, tokens_out=1, cost_estimate_usd=0.0, latency_ms=0
        )

    def complete_structured(
        self,
        prompt: str,
        *,
        model: str,
        response_schema: type[SchemaT],
        temperature: float = 0.0,
    ) -> StructuredLLMResponse[SchemaT]:
        """Validate the scripted response against response_schema and return it."""
        self.last_prompt = prompt
        parsed = response_schema.model_validate(self._structured_response.model_dump())
        return StructuredLLMResponse(
            text="fake",
            parsed=parsed,
            tokens_in=10,
            tokens_out=5,
            cost_estimate_usd=0.0,
            latency_ms=1,
        )


@pytest.fixture
def fake_llm_factory() -> Callable[[BaseModel], FakeLLMProvider]:
    """Return a factory building a FakeLLMProvider from a scripted response."""
    return FakeLLMProvider


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    """A Session bound to a fresh, file-based scratch SQLite DB, all tables created.

    A real temp file (not ``:memory:``) sidesteps the classic SQLAlchemy
    gotcha where an in-memory SQLite URL gives each pooled connection
    its own separate, empty database unless a StaticPool is configured
    -- a file-based scratch DB behaves like production with no special
    casing needed. Lives at the repo-wide conftest level (not just
    tests/storage/) since agent/orchestration/CLI tests need it too.
    """
    engine = create_sqlite_engine(tmp_path / "test.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


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
