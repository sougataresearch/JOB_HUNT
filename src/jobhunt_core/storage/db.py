"""SQLAlchemy engine/session setup (database.md, decisions.md ADR-0002)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_BUSY_TIMEOUT_MS = 5000


def create_sqlite_engine(db_path: Path | str, *, echo: bool = False) -> Engine:
    """Create a SQLite engine with WAL mode, a busy timeout, and FK enforcement.

    All three pragmas are applied on every new DBAPI connection
    (SQLAlchemy pools connections, and none of these three are
    persisted in the database file itself). WAL mode + busy_timeout
    close the concurrent-writer gap flagged in final_review.md §1.1:
    without them, a background ``/scrape`` writing while an
    interactive ``/apply`` also writes would risk "database is locked"
    errors under SQLite's default rollback-journal mode. SQLite does
    not enforce declared foreign keys unless ``PRAGMA foreign_keys=ON``
    is set per-connection -- without it, the FK constraints in
    database.md/storage/models/ would be documentation only, not
    actually enforced (tasks.md T4.2: "Constraints (unique, FK) match
    database.md exactly").

    Args:
        db_path: Path to the SQLite file, or ``":memory:"`` for an
            in-memory database (tests).
        echo: Passed through to ``create_engine`` for SQL logging.

    Returns:
        A configured ``Engine``.
    """
    engine = create_engine(f"sqlite:///{db_path}", echo=echo)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a session factory bound to ``engine``."""
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a transactional scope: commit on success, rollback on error.

    Args:
        session_factory: A factory from :func:`create_session_factory`.

    Yields:
        A ``Session`` for the duration of the ``with`` block.
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
