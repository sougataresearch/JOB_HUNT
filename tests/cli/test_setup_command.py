"""Tests for `jobhunt setup` (tasks.md T5.3).

``run_setup_with_context`` is exercised directly with a fake LLM
provider (no live call). ``run_setup`` itself (which loads real
Settings and runs a real Alembic migration) is exercised against a
scratch data directory to prove the end-to-end wiring -- including a
real ``alembic upgrade head`` -- works, still with a faked LLM call.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from cli.commands.setup import ensure_migrated, run_setup, run_setup_with_context
from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
from jobhunt_core.schemas.profile import CandidateProfileExtraction
from jobhunt_core.storage.repositories import (
    ApplicationRepo,
    ATSRepo,
    InterviewRepo,
    JobRepo,
    MatchRepo,
    ProfileRepo,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "cvs"

_EXTRACTION = CandidateProfileExtraction(full_name="Jane Doe", email="jane.doe@example.com")


def test_run_setup_with_context_persists_profile(db_session: Session, fake_llm_factory) -> None:
    """run_setup_with_context() runs the agent and saves the result."""
    settings = Settings(
        llm=LLMConfig(default_provider="fake", providers={}),
        agents={"resume_analysis": AgentConfig(enabled=True, provider="fake", model="fake-model")},
        sources={},
    )
    repos = RepositoryBundle(
        profiles=ProfileRepo(db_session),
        jobs=JobRepo(db_session),
        matches=MatchRepo(db_session),
        ats=ATSRepo(db_session),
        applications=ApplicationRepo(db_session),
        interviews=InterviewRepo(db_session),
    )
    ctx = RunContext(settings=settings, llm=fake_llm_factory(_EXTRACTION), repos=repos)

    profile = run_setup_with_context(FIXTURES_DIR / "jane_doe_complete.md", ctx)

    assert profile.id is not None
    fetched = ctx.repos.profiles.get(profile.id)
    assert fetched is not None
    assert fetched.full_name == "Jane Doe"


def test_ensure_migrated_creates_working_database(tmp_path: Path) -> None:
    """ensure_migrated() runs a real alembic upgrade against a scratch data dir."""
    ensure_migrated(tmp_path)

    from sqlalchemy import create_engine, inspect

    engine = create_engine(f"sqlite:///{tmp_path / 'jobhunt.db'}")
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert "candidate_profiles" in tables


def test_run_setup_end_to_end_with_fake_provider(
    tmp_path: Path, monkeypatch, fake_llm_factory
) -> None:
    """run_setup() end-to-end: real migration + real DB, faked LLM call only.

    Injects Settings directly (bypassing load_settings()'s YAML/env
    loading) so no real API key or config/ files are needed -- the
    only thing faked is the LLM call itself.
    """
    from jobhunt_core.orchestration import context as context_module

    settings = Settings(
        llm=LLMConfig(default_provider="fake", providers={}),
        agents={"resume_analysis": AgentConfig(enabled=True, provider="fake", model="fake-model")},
        sources={},
        data_dir=tmp_path,
    )
    fake_llm = fake_llm_factory(_EXTRACTION)

    monkeypatch.setattr(
        context_module, "build_llm_provider", lambda provider_name, settings: fake_llm
    )

    profile = run_setup(FIXTURES_DIR / "jane_doe_complete.md", settings=settings)

    assert profile.id is not None
    assert profile.full_name == "Jane Doe"
    assert (tmp_path / "jobhunt.db").exists()
