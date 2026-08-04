"""Shared fixtures for storage-layer tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from jobhunt_core.storage.db import create_session_factory, create_sqlite_engine
from jobhunt_core.storage.models import Base


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    """A Session bound to a fresh, file-based scratch SQLite DB, all tables created.

    A real temp file (not ``:memory:``) sidesteps the classic SQLAlchemy
    gotcha where an in-memory SQLite URL gives each pooled connection
    its own separate, empty database unless a StaticPool is configured
    -- a file-based scratch DB behaves like production with no special
    casing needed.
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
