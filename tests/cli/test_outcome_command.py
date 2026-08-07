"""Tests for `jobhunt outcome` (tasks.md T14.3).

No LLM faking needed at all: ``_build_tracking_context`` never
constructs a real ``LLMProvider`` in the first place (agents.md §9 --
Application Tracking Agent is deterministic), so ``run_outcome``'s
end-to-end path (real migration, real DB) needs no monkeypatching
unlike ``run_setup``'s equivalent test.
"""

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from cli.commands.outcome import (
    _build_tracking_context,
    ensure_migrated,
    run_outcome,
    run_outcome_with_context,
)
from jobhunt_core.config.settings import LLMConfig, Settings
from jobhunt_core.errors import JobHuntError
from jobhunt_core.schemas.application import Application, ApplicationStatus
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.storage.db import create_session_factory, create_sqlite_engine
from jobhunt_core.storage.repositories import ApplicationRepo, JobRepo


def test_run_outcome_with_context_transitions_status(db_session: Session) -> None:
    """The happy path against an in-memory-style scratch DB, no real migration involved."""
    settings = Settings(llm=LLMConfig(default_provider="fake", providers={}), agents={}, sources={})
    ctx = _build_tracking_context(settings, db_session)
    posting = JobRepo(db_session).save(
        JobPosting(source="greenhouse", source_id="1", title="Engineer", url="https://x/1")
    )
    ApplicationRepo(db_session).create(Application(job_posting_id=posting.id))

    application = run_outcome_with_context(
        posting.id, ApplicationStatus.SUBMITTED, "Sent via email", ctx
    )

    assert application.status == ApplicationStatus.SUBMITTED


def test_run_outcome_with_context_raises_for_unknown_posting(db_session: Session) -> None:
    settings = Settings(llm=LLMConfig(default_provider="fake", providers={}), agents={}, sources={})
    ctx = _build_tracking_context(settings, db_session)

    with pytest.raises(JobHuntError, match="No job posting"):
        run_outcome_with_context("does-not-exist", ApplicationStatus.SUBMITTED, None, ctx)


def test_run_outcome_with_context_raises_when_no_application_yet(db_session: Session) -> None:
    settings = Settings(llm=LLMConfig(default_provider="fake", providers={}), agents={}, sources={})
    ctx = _build_tracking_context(settings, db_session)
    posting = JobRepo(db_session).save(
        JobPosting(source="greenhouse", source_id="1", title="Engineer", url="https://x/1")
    )

    with pytest.raises(JobHuntError, match="No application exists"):
        run_outcome_with_context(posting.id, ApplicationStatus.SUBMITTED, None, ctx)


def test_run_outcome_end_to_end_with_real_migration(tmp_path: Path) -> None:
    """run_outcome(): real alembic migration + real DB, no LLM ever built at all."""
    settings = Settings(
        llm=LLMConfig(default_provider="fake", providers={}),
        agents={},
        sources={},
        data_dir=tmp_path,
    )

    ensure_migrated(tmp_path)
    engine = create_sqlite_engine(tmp_path / "jobhunt.db")
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        posting = JobRepo(session).save(
            JobPosting(source="greenhouse", source_id="1", title="Engineer", url="https://x/1")
        )
        ApplicationRepo(session).create(Application(job_posting_id=posting.id))
        session.commit()
        job_posting_id = posting.id
    finally:
        session.close()
        engine.dispose()

    application = run_outcome(job_posting_id, ApplicationStatus.SUBMITTED, settings=settings)

    assert application.status == ApplicationStatus.SUBMITTED
    assert (tmp_path / "jobhunt.db").exists()
