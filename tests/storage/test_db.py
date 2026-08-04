"""Tests for storage/db.py (final_review.md §1.1: WAL mode + busy timeout)."""

from pathlib import Path

from jobhunt_core.storage.db import create_sqlite_engine


def test_sqlite_engine_enables_wal_mode(tmp_path: Path) -> None:
    """The engine's connections use WAL journal mode, not the default rollback journal."""
    engine = create_sqlite_engine(tmp_path / "test.db")

    with engine.connect() as conn:
        (mode,) = conn.exec_driver_sql("PRAGMA journal_mode").fetchone()

    assert mode == "wal"


def test_sqlite_engine_sets_busy_timeout(tmp_path: Path) -> None:
    """The engine's connections have a non-zero busy_timeout set."""
    engine = create_sqlite_engine(tmp_path / "test.db")

    with engine.connect() as conn:
        (timeout_ms,) = conn.exec_driver_sql("PRAGMA busy_timeout").fetchone()

    assert timeout_ms == 5000


def test_sqlite_engine_enforces_foreign_keys(tmp_path: Path) -> None:
    """The engine's connections have foreign_keys enforcement on (tasks.md T4.2)."""
    engine = create_sqlite_engine(tmp_path / "test.db")

    with engine.connect() as conn:
        (enabled,) = conn.exec_driver_sql("PRAGMA foreign_keys").fetchone()

    assert enabled == 1
