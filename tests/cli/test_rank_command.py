"""Tests for `jobhunt rank` (tasks.md T9.1).

No LLM anywhere in this command (``orchestration/ranking.py`` is a
pure function, api.md §3) -- these tests use real repos against a
scratch DB, no fake provider needed.
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from cli.commands.rank import run_rank, run_rank_with_session
from jobhunt_core.config.settings import LLMConfig, Settings
from jobhunt_core.errors import JobHuntError
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.match import MatchScore
from jobhunt_core.schemas.profile import CandidateProfile
from jobhunt_core.storage.repositories import JobRepo, MatchRepo, ProfileRepo


def _save_profile_posting_and_score(session: Session, *, score: float, source_id: str) -> None:
    profile = ProfileRepo(session).get_active()
    if profile is None:
        new_profile = CandidateProfile(full_name="Jordan Lee", is_active=True)
        profile = ProfileRepo(session).save(new_profile)
    posting = JobRepo(session).save(
        JobPosting(
            source="greenhouse",
            source_id=source_id,
            title="Backend Engineer",
            url=f"https://example.com/jobs/{source_id}",
        )
    )
    MatchRepo(session).save(
        MatchScore(
            job_posting_id=posting.id,
            profile_id=profile.id,
            score=score,
            rationale="because",
        )
    )


def test_run_rank_with_session_returns_ranked_page(db_session: Session) -> None:
    """A ranked page reflects saved scores, best match first."""
    _save_profile_posting_and_score(db_session, score=40.0, source_id="1")
    _save_profile_posting_and_score(db_session, score=90.0, source_id="2")

    page = run_rank_with_session(db_session)

    assert len(page) == 2
    assert page[0].score.score == 90.0
    assert page[0].rank == 1
    assert page[1].score.score == 40.0


def test_run_rank_with_session_paginates(db_session: Session) -> None:
    """page/page_size are honored."""
    for i in range(3):
        _save_profile_posting_and_score(db_session, score=float(90 - i * 10), source_id=str(i))

    page = run_rank_with_session(db_session, page=1, page_size=2)

    assert len(page) == 2


def test_run_rank_with_session_raises_without_active_profile(db_session: Session) -> None:
    """No active candidate profile is a clear, actionable error, not a crash."""
    with pytest.raises(JobHuntError, match="No active candidate profile"):
        run_rank_with_session(db_session)


def test_run_rank_end_to_end_with_scratch_db(tmp_path: Path) -> None:
    """run_rank() end-to-end: real migration + real DB, no LLM at all."""
    settings = Settings(
        llm=LLMConfig(default_provider="anthropic", providers={}),
        agents={},
        sources={},
        data_dir=tmp_path,
    )

    from cli.commands.rank import ensure_migrated
    from jobhunt_core.storage.db import create_session_factory, create_sqlite_engine

    ensure_migrated(tmp_path)
    engine = create_sqlite_engine(tmp_path / "jobhunt.db")
    session = create_session_factory(engine)()
    try:
        _save_profile_posting_and_score(session, score=75.0, source_id="1")
        session.commit()
    finally:
        session.close()
        engine.dispose()

    page = run_rank(settings=settings)

    assert len(page) == 1
    assert page[0].score.score == 75.0

    check_engine = create_engine(f"sqlite:///{tmp_path / 'jobhunt.db'}")
    try:
        assert "match_scores" in inspect(check_engine).get_table_names()
    finally:
        check_engine.dispose()
