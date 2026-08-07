"""Tests for `jobhunt interview` (tasks.md T15.1, phases.md Phase 15).

``run_interview_with_context`` is exercised directly with a fake LLM
provider (no live call), same pattern as ``tests/cli/test_setup_command.py``.
"""

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from cli.commands.interview import run_interview_with_context
from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
from jobhunt_core.errors import JobHuntError
from jobhunt_core.schemas.application import Application, ApplicationStatus
from jobhunt_core.schemas.document import ResumeVersion
from jobhunt_core.schemas.interview import (
    InterviewPrepExtraction,
    InterviewQuestionDraft,
    InterviewType,
    QuestionCategory,
)
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.match import MatchScore
from jobhunt_core.schemas.profile import CandidateProfile
from jobhunt_core.storage.repositories import (
    ApplicationRepo,
    ATSRepo,
    DocumentRepo,
    InterviewRepo,
    JobRepo,
    MatchRepo,
    ProfileRepo,
)

_QUESTIONS = InterviewPrepExtraction(
    questions=[
        InterviewQuestionDraft(
            category=QuestionCategory.TECHNICAL,
            question="Tell me about a recent project.",
            suggested_talking_points=["Built APIs serving 1M requests/day"],
        )
    ]
)


def _make_context(db_session: Session, llm: object) -> RunContext:
    settings = Settings(
        llm=LLMConfig(default_provider="fake", providers={}),
        agents={"interview_prep": AgentConfig(enabled=True, provider="fake", model="fake-model")},
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
    return RunContext(settings=settings, llm=llm, repos=repos)  # type: ignore[arg-type]


def _seed_ready_application(db_session: Session, tmp_path: Path) -> str:
    """A posting with an interview_scheduled application, resume version, and match score."""
    posting = JobRepo(db_session).save(
        JobPosting(
            source="greenhouse",
            source_id="1",
            title="Engineer",
            url="https://example.com/1",
            normalized_description="Backend role building distributed systems in Python and AWS.",
        )
    )
    profile = ProfileRepo(db_session).save(CandidateProfile(full_name="Jane Doe"))
    documents = DocumentRepo(db_session)
    template = documents.get_or_create_template(
        kind="resume", name="resume", file_path="cv/resume.tex.jinja"
    )
    extracted_text_path = tmp_path / "resume.extracted.txt"
    extracted_text_path.write_text(
        "Jane Doe\nBuilt APIs serving 1M requests/day\n", encoding="utf-8"
    )
    resume_version = documents.save_resume_version(
        ResumeVersion(
            profile_id=profile.id,
            job_posting_id=posting.id,
            template_id=template.id or "",
            rendered_pdf_path="r.pdf",
            rendered_tex_path="r.tex",
            ats_verification_passed=True,
            ats_extracted_text_path=str(extracted_text_path),
        )
    )
    MatchRepo(db_session).save(
        MatchScore(
            job_posting_id=posting.id, profile_id=profile.id, score=80.0, rationale="Good fit."
        )
    )
    application = ApplicationRepo(db_session).create(
        Application(job_posting_id=posting.id, resume_version_id=resume_version.id)
    )
    ApplicationRepo(db_session).change_status(application.id, ApplicationStatus.INTERVIEW_SCHEDULED)
    return posting.id


def test_run_interview_with_context_happy_path(
    db_session: Session, fake_llm_factory, tmp_path: Path
) -> None:
    job_posting_id = _seed_ready_application(db_session, tmp_path)
    ctx = _make_context(db_session, fake_llm_factory(_QUESTIONS))

    pack = run_interview_with_context(job_posting_id, InterviewType.PHONE_SCREEN, ctx)

    assert pack.interview.id is not None
    assert len(pack.questions) == 1


def test_run_interview_with_context_raises_for_unknown_posting(
    db_session: Session, fake_llm_factory
) -> None:
    ctx = _make_context(db_session, fake_llm_factory(_QUESTIONS))

    with pytest.raises(JobHuntError, match="No job posting"):
        run_interview_with_context("does-not-exist", InterviewType.PHONE_SCREEN, ctx)


def test_run_interview_with_context_raises_when_no_application(
    db_session: Session, fake_llm_factory
) -> None:
    posting = JobRepo(db_session).save(
        JobPosting(source="greenhouse", source_id="1", title="Engineer", url="https://x/1")
    )
    ctx = _make_context(db_session, fake_llm_factory(_QUESTIONS))

    with pytest.raises(JobHuntError, match="No application exists"):
        run_interview_with_context(posting.id, InterviewType.PHONE_SCREEN, ctx)


def test_run_interview_with_context_raises_when_not_interview_scheduled(
    db_session: Session, fake_llm_factory
) -> None:
    posting = JobRepo(db_session).save(
        JobPosting(source="greenhouse", source_id="1", title="Engineer", url="https://x/1")
    )
    ApplicationRepo(db_session).create(Application(job_posting_id=posting.id))
    ctx = _make_context(db_session, fake_llm_factory(_QUESTIONS))

    with pytest.raises(JobHuntError, match="not 'interview_scheduled'"):
        run_interview_with_context(posting.id, InterviewType.PHONE_SCREEN, ctx)


def test_run_interview_with_context_raises_when_no_resume_version(
    db_session: Session, fake_llm_factory
) -> None:
    posting = JobRepo(db_session).save(
        JobPosting(source="greenhouse", source_id="1", title="Engineer", url="https://x/1")
    )
    application = ApplicationRepo(db_session).create(Application(job_posting_id=posting.id))
    ApplicationRepo(db_session).change_status(application.id, ApplicationStatus.INTERVIEW_SCHEDULED)
    ctx = _make_context(db_session, fake_llm_factory(_QUESTIONS))

    with pytest.raises(JobHuntError, match="no linked resume version"):
        run_interview_with_context(posting.id, InterviewType.PHONE_SCREEN, ctx)
