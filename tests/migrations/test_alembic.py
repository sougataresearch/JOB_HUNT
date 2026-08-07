"""Alembic upgrade/downgrade round-trip (phases.md Phase 4 acceptance criteria).

Runs the real ``alembic`` commands against a scratch, gitignored temp
directory (via ``JOBHUNT_DATA_DIR``, the same env var
``migrations/env.py`` and ``Settings`` both honor) -- never against
the developer's real ``data/jobhunt.db``.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

REPO_ROOT = Path(__file__).resolve().parents[2]

_EXPECTED_TABLES = {
    "candidate_profiles",
    "companies",
    "job_postings",
    "applications",
    "application_events",
    "ats_reports",
    "match_scores",
    "interviews",
    "interview_questions",
    "search_runs",
    "templates",
    "resume_versions",
    "cover_letters",
}


@pytest.fixture
def alembic_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    """An Alembic Config pointed at this repo's migrations, writing to tmp_path."""
    monkeypatch.setenv("JOBHUNT_DATA_DIR", str(tmp_path))
    return Config(str(REPO_ROOT / "alembic.ini"))


def _table_names(tmp_path: Path) -> set[str]:
    engine = create_engine(f"sqlite:///{tmp_path / 'jobhunt.db'}")
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_head_creates_every_table(alembic_config: Config, tmp_path: Path) -> None:
    """alembic upgrade head creates every table declared in the models."""
    command.upgrade(alembic_config, "head")

    tables = _table_names(tmp_path)

    assert _EXPECTED_TABLES <= tables
    assert "alembic_version" in tables


def test_downgrade_base_drops_every_table(alembic_config: Config, tmp_path: Path) -> None:
    """alembic downgrade base removes every table the initial migration created."""
    command.upgrade(alembic_config, "head")

    command.downgrade(alembic_config, "base")

    tables = _table_names(tmp_path)
    assert not (_EXPECTED_TABLES & tables)


def test_0002_adds_search_run_id_fk_to_job_postings(alembic_config: Config, tmp_path: Path) -> None:
    """Phase 7's migration adds job_postings.search_run_id as an FK to search_runs.

    SQLite can't ALTER TABLE ADD CONSTRAINT directly (migrations/env.py's
    render_as_batch=True note) -- this proves the batch-mode migration
    actually produces a working FK column, not just that it runs
    without raising.
    """
    command.upgrade(alembic_config, "head")

    engine = create_engine(f"sqlite:///{tmp_path / 'jobhunt.db'}")
    try:
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("job_postings")}
        fks = inspector.get_foreign_keys("job_postings")
    finally:
        engine.dispose()

    assert "search_run_id" in columns
    assert any(fk["referred_table"] == "search_runs" for fk in fks)


def test_downgrade_to_0001_then_upgrade_head_round_trips(
    alembic_config: Config, tmp_path: Path
) -> None:
    """Downgrading one step (past the batch-mode migration) and back is lossless."""
    command.upgrade(alembic_config, "head")

    command.downgrade(alembic_config, "0001")
    tables_after_downgrade = _table_names(tmp_path)
    assert "search_runs" not in tables_after_downgrade

    command.upgrade(alembic_config, "head")
    tables_after_reupgrade = _table_names(tmp_path)
    assert "search_runs" in tables_after_reupgrade


def test_0003_adds_templates_and_resume_versions(alembic_config: Config, tmp_path: Path) -> None:
    """Phase 11's migration adds templates and resume_versions with working FKs."""
    command.upgrade(alembic_config, "head")

    engine = create_engine(f"sqlite:///{tmp_path / 'jobhunt.db'}")
    try:
        inspector = inspect(engine)
        resume_version_fks = {
            fk["referred_table"] for fk in inspector.get_foreign_keys("resume_versions")
        }
    finally:
        engine.dispose()

    assert resume_version_fks == {"candidate_profiles", "job_postings", "templates"}


def test_0004_adds_cover_letters(alembic_config: Config, tmp_path: Path) -> None:
    """Phase 12's migration adds cover_letters with working FKs."""
    command.upgrade(alembic_config, "head")

    engine = create_engine(f"sqlite:///{tmp_path / 'jobhunt.db'}")
    try:
        inspector = inspect(engine)
        cover_letter_fks = {
            fk["referred_table"] for fk in inspector.get_foreign_keys("cover_letters")
        }
    finally:
        engine.dispose()

    assert cover_letter_fks == {"applications", "job_postings", "resume_versions", "templates"}


def test_0005_adds_application_document_links(alembic_config: Config, tmp_path: Path) -> None:
    """Phase 14's migration adds applications.resume_version_id/cover_letter_id as working FKs."""
    command.upgrade(alembic_config, "head")

    engine = create_engine(f"sqlite:///{tmp_path / 'jobhunt.db'}")
    try:
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("applications")}
        fks = {fk["referred_table"] for fk in inspector.get_foreign_keys("applications")}
    finally:
        engine.dispose()

    assert {"resume_version_id", "cover_letter_id"} <= columns
    assert {"resume_versions", "cover_letters"} <= fks
