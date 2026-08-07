"""Tests for the Email Generation Agent (tasks.md T13.1, phases.md Phase 13).

Uses ``FakeLLMProvider`` (tests/conftest.py) -- a single LLM call, no
drafter->reviewer loop (agents.md §8 Retry logic: "Shared LLM retry
policy only"), and no persistence (agents.md §8 Memory: "writes
nothing persisted independently in v1").
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.agents.email_generation_agent import (
    EmailGenerationAgent,
    EmailGenerationInput,
)
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
from jobhunt_core.llm.provider import LLMProvider
from jobhunt_core.schemas.document import CoverLetter, ResumeVersion
from jobhunt_core.schemas.email import EmailDraftExtraction
from jobhunt_core.schemas.job import JobPosting
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


def _make_context(db_session: Session, llm: LLMProvider) -> RunContext:
    settings = Settings(
        llm=LLMConfig(default_provider="fake", providers={}),
        agents={"email_generation": AgentConfig(enabled=True, provider="fake", model="fake-model")},
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


def _posting(**overrides: object) -> JobPosting:
    defaults: dict = dict(
        id="posting-1",
        source="greenhouse",
        source_id="1",
        title="Backend Engineer",
        url="https://example.com/jobs/1",
        normalized_description="Join our Platform team as a Backend Engineer.",
    )
    defaults.update(overrides)
    return JobPosting(**defaults)


def _resume_version(**overrides: object) -> ResumeVersion:
    defaults: dict = dict(
        id="resume-version-1",
        profile_id="profile-1",
        job_posting_id="posting-1",
        template_id="template-1",
        rendered_pdf_path="/data/documents/resumes/x/resume.pdf",
        rendered_tex_path="/data/documents/resumes/x/resume.tex",
        ats_verification_passed=True,
        ats_extracted_text_path="/data/documents/resumes/x/resume.extracted.txt",
    )
    defaults.update(overrides)
    return ResumeVersion(**defaults)


def _cover_letter(**overrides: object) -> CoverLetter:
    defaults: dict = dict(
        id="cover-letter-1",
        job_posting_id="posting-1",
        resume_version_id="resume-version-1",
        template_id="template-2",
        rendered_pdf_path="/data/documents/cover_letters/x/cover_letter.pdf",
        rendered_tex_path="/data/documents/cover_letters/x/cover_letter.tex",
    )
    defaults.update(overrides)
    return CoverLetter(**defaults)


def test_run_extracts_recipient_and_assembles_attachments(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """Happy path: a recipient found in posting text, attachments assembled deterministically."""
    extraction = EmailDraftExtraction(
        to="jobs@acme.com", subject="Application for Backend Engineer", body="Please see attached."
    )
    llm = fake_llm_factory(extraction)
    ctx = _make_context(db_session, llm)
    agent = EmailGenerationAgent()

    result = agent.run(
        EmailGenerationInput(
            job_posting=_posting(),
            resume_version=_resume_version(),
            cover_letter=_cover_letter(),
        ),
        ctx,
    )

    assert result.output.to == "jobs@acme.com"
    assert result.output.status == "draft"
    assert result.output.attachments == [
        Path("/data/documents/resumes/x/resume.pdf"),
        Path("/data/documents/cover_letters/x/cover_letter.pdf"),
    ]
    assert result.warnings == []


def test_run_never_guesses_a_missing_recipient(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """agents.md §8 Failure handling: to=None + explicit warning, never a guessed address."""
    extraction = EmailDraftExtraction(to=None, subject="Application", body="Please see attached.")
    llm = fake_llm_factory(extraction)
    ctx = _make_context(db_session, llm)
    agent = EmailGenerationAgent()

    result = agent.run(
        EmailGenerationInput(
            job_posting=_posting(),
            resume_version=_resume_version(),
            cover_letter=_cover_letter(),
        ),
        ctx,
    )

    assert result.output.to is None
    assert any("No recipient email address" in warning for warning in result.warnings)


def test_run_raises_when_resume_version_belongs_to_different_posting(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """A mismatched ResumeVersion/JobPosting pairing must never be silently assembled."""
    extraction = EmailDraftExtraction(to=None, subject="Application", body="Body.")
    llm = fake_llm_factory(extraction)
    ctx = _make_context(db_session, llm)
    agent = EmailGenerationAgent()
    mismatched_resume = _resume_version(job_posting_id="a-different-posting")

    with pytest.raises(ValueError, match="job_posting_id"):
        agent.run(
            EmailGenerationInput(
                job_posting=_posting(),
                resume_version=mismatched_resume,
                cover_letter=_cover_letter(),
            ),
            ctx,
        )


def test_run_raises_when_cover_letter_belongs_to_different_posting(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """Same defensive check for the cover letter side of the pairing."""
    extraction = EmailDraftExtraction(to=None, subject="Application", body="Body.")
    llm = fake_llm_factory(extraction)
    ctx = _make_context(db_session, llm)
    agent = EmailGenerationAgent()
    mismatched_cover_letter = _cover_letter(job_posting_id="a-different-posting")

    with pytest.raises(ValueError, match="job_posting_id"):
        agent.run(
            EmailGenerationInput(
                job_posting=_posting(),
                resume_version=_resume_version(),
                cover_letter=mismatched_cover_letter,
            ),
            ctx,
        )
