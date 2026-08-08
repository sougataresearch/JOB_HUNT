"""Tests for `jobhunt report` (tasks.md T16.2).

No LLM faking needed at all: ``_build_analytics_context`` never
constructs a real ``LLMProvider`` (agents.md §11 -- Career Analytics is
deterministic), same reasoning as ``cli/commands/outcome.py``.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from cli.commands.report import _build_analytics_context, run_report, run_report_with_context
from jobhunt_core.config.settings import LLMConfig, Settings
from jobhunt_core.schemas.application import Application, ApplicationStatus
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.storage.db import create_session_factory, create_sqlite_engine
from jobhunt_core.storage.repositories import ApplicationRepo, JobRepo


def test_run_report_with_context_reflects_seeded_applications(db_session: Session) -> None:
    settings = Settings(llm=LLMConfig(default_provider="fake", providers={}), agents={}, sources={})
    ctx = _build_analytics_context(settings, db_session)
    posting = JobRepo(db_session).save(
        JobPosting(source="greenhouse", source_id="1", title="Engineer", url="https://x/1")
    )
    ApplicationRepo(db_session).create(
        Application(job_posting_id=posting.id, status=ApplicationStatus.SUBMITTED)
    )

    report = run_report_with_context(ctx)

    assert report.total_applications == 1
    assert report.insufficient_data is True  # only 1 submitted, below the 5-application floor


def test_run_report_end_to_end_writes_html_file(tmp_path: Path) -> None:
    """run_report(): real alembic migration + real DB, no LLM ever built at all."""
    settings = Settings(
        llm=LLMConfig(default_provider="fake", providers={}),
        agents={},
        sources={},
        data_dir=tmp_path,
    )

    from cli.commands.report import ensure_migrated

    ensure_migrated(tmp_path)
    engine = create_sqlite_engine(tmp_path / "jobhunt.db")
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        posting = JobRepo(session).save(
            JobPosting(source="greenhouse", source_id="1", title="Engineer", url="https://x/1")
        )
        ApplicationRepo(session).create(
            Application(job_posting_id=posting.id, status=ApplicationStatus.SUBMITTED)
        )
        session.commit()
    finally:
        session.close()
        engine.dispose()

    output_path = run_report(settings=settings)

    assert output_path == tmp_path / "report.html"
    assert output_path.exists()
    assert "JOB_HUNT Career Analytics" in output_path.read_text(encoding="utf-8")
