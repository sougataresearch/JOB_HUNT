"""Tests for the Resume Analysis Agent (tasks.md T5.2, phases.md Phase 5).

Uses the ``fake_llm_factory`` fixture (tests/conftest.py) throughout --
no live LLM calls. These tests verify the *agent's own logic* (file
dispatch, prompt rendering, response assembly, persistence) is correct
given a scripted LLM response; they cannot verify real extraction
quality, which requires a live model call this environment has no
credentials for (same caveat as Phase 3's provider tests -- see
progress_log.md).
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.agents.resume_analysis_agent import ResumeAnalysisAgent, ResumeAnalysisInput
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
from jobhunt_core.errors import UnsupportedFormatError
from jobhunt_core.llm.provider import LLMProvider
from jobhunt_core.schemas.profile import CandidateProfileExtraction, ExperienceEntry
from jobhunt_core.storage.repositories import (
    ApplicationRepo,
    ATSRepo,
    DocumentRepo,
    InterviewRepo,
    JobRepo,
    MatchRepo,
    ProfileRepo,
)

FakeLLMFactory = Callable[[BaseModel], LLMProvider]

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "cvs"

_JANE_EXTRACTION = CandidateProfileExtraction(
    full_name="Jane Doe",
    email="jane.doe@example.com",
    location="Seattle, WA",
    summary="Backend engineer with 6 years of experience.",
    skills=["Python", "Go", "PostgreSQL", "Kubernetes", "AWS"],
    experience=[
        ExperienceEntry(
            title="Senior Software Engineer",
            company="Acme Corp",
            start_date="2021",
            end_date="2024",
            bullets=["Led migration of the payments service to microservices."],
        )
    ],
    certifications=["AWS Certified Solutions Architect"],
)

_SPARSE_EXTRACTION = CandidateProfileExtraction(
    full_name="A. Candidate",
    # Everything else genuinely wasn't in the source CV -- left unset,
    # matching CandidateProfileExtraction's all-Optional defaults.
)


def _make_context(db_session: Session, llm: LLMProvider) -> RunContext:
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
        documents=DocumentRepo(db_session),
    )
    return RunContext(settings=settings, llm=llm, repos=repos)


def test_run_produces_candidate_profile_from_markdown_cv(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """Given a scripted extraction, run() assembles a full CandidateProfile."""
    ctx = _make_context(db_session, fake_llm_factory(_JANE_EXTRACTION))
    agent = ResumeAnalysisAgent()
    cv_path = FIXTURES_DIR / "jane_doe_complete.md"

    result = agent.run(ResumeAnalysisInput(cv_file_path=cv_path), ctx)

    assert result.output.full_name == "Jane Doe"
    assert result.output.email == "jane.doe@example.com"
    assert result.output.skills == ["Python", "Go", "PostgreSQL", "Kubernetes", "AWS"]
    assert result.output.source_file_path == str(cv_path)
    assert result.model == "fake-model"
    assert result.prompt_version == "1.0"


def test_run_persists_via_repository(db_session: Session, fake_llm_factory: FakeLLMFactory) -> None:
    """The agent's output can be saved and read back through ProfileRepo."""
    ctx = _make_context(db_session, fake_llm_factory(_JANE_EXTRACTION))
    agent = ResumeAnalysisAgent()
    cv_path = FIXTURES_DIR / "jane_doe_complete.md"

    result = agent.run(ResumeAnalysisInput(cv_file_path=cv_path), ctx)
    saved = ctx.repos.profiles.save(result.output)
    fetched = ctx.repos.profiles.get(saved.id)

    assert fetched is not None
    assert fetched.full_name == "Jane Doe"


def test_run_works_across_all_three_formats(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """The same scripted extraction round-trips regardless of source file format."""
    for ext in ("md", "docx", "pdf"):
        ctx = _make_context(db_session, fake_llm_factory(_JANE_EXTRACTION))
        agent = ResumeAnalysisAgent()
        cv_path = FIXTURES_DIR / f"jane_doe_complete.{ext}"

        result = agent.run(ResumeAnalysisInput(cv_file_path=cv_path), ctx)

        assert result.output.full_name == "Jane Doe"
        assert result.output.source_file_path == str(cv_path)


def test_sparse_cv_never_fabricates_missing_fields(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """A profile built from a sparse extraction leaves unset fields unset, not guessed.

    This tests that the agent passes through whatever the LLM (real or
    fake) returns without adding anything of its own -- it does not
    (and cannot, without a live call) verify that a real LLM actually
    behaves this way for this specific sparse CV; that's a prompt-
    quality question outside this test's reach.
    """
    ctx = _make_context(db_session, fake_llm_factory(_SPARSE_EXTRACTION))
    agent = ResumeAnalysisAgent()
    cv_path = FIXTURES_DIR / "sparse_partial.md"

    result = agent.run(ResumeAnalysisInput(cv_file_path=cv_path), ctx)

    assert result.output.full_name == "A. Candidate"
    assert result.output.email is None
    assert result.output.phone is None
    assert result.output.education == []
    assert result.output.skills == []


def test_run_raises_on_unsupported_file_extension(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """An unsupported CV file extension surfaces UnsupportedFormatError."""
    ctx = _make_context(db_session, fake_llm_factory(_JANE_EXTRACTION))
    agent = ResumeAnalysisAgent()

    with pytest.raises(UnsupportedFormatError):
        agent.run(ResumeAnalysisInput(cv_file_path=Path("resume.exe")), ctx)


def test_prompt_sent_to_llm_contains_cv_text(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """The rendered prompt actually includes the parsed CV's raw text."""
    llm = fake_llm_factory(_JANE_EXTRACTION)
    ctx = _make_context(db_session, llm)
    agent = ResumeAnalysisAgent()
    cv_path = FIXTURES_DIR / "jane_doe_complete.md"

    agent.run(ResumeAnalysisInput(cv_file_path=cv_path), ctx)

    assert llm.last_prompt is not None  # type: ignore[attr-defined]
    assert "Jane Doe" in llm.last_prompt  # type: ignore[attr-defined]
    assert "AWS Certified Solutions Architect" in llm.last_prompt  # type: ignore[attr-defined]
