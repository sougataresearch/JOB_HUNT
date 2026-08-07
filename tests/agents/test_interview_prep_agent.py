"""Tests for the Interview Prep Agent (tasks.md T15.1, phases.md Phase 15).

Uses ``FakeLLMProvider`` (tests/conftest.py) -- a single LLM call, no
drafter->reviewer loop (agents.md §10 Retry logic: "Shared LLM retry
policy only").
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.agents.interview_prep_agent import InterviewPrepAgent, InterviewPrepInput
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
from jobhunt_core.llm.provider import LLMProvider
from jobhunt_core.schemas.application import Application
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

FakeLLMFactory = Callable[[BaseModel], LLMProvider]


def _make_context(db_session: Session, llm: LLMProvider) -> RunContext:
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
    return RunContext(settings=settings, llm=llm, repos=repos)


def _seed(
    db_session: Session, tmp_path: Path, *, posting_text: str
) -> tuple[Application, JobPosting, ResumeVersion, MatchScore]:
    posting = JobRepo(db_session).save(
        JobPosting(
            source="greenhouse",
            source_id="1",
            title="Backend Engineer",
            url="https://example.com/1",
            normalized_description=posting_text,
        )
    )
    profile = ProfileRepo(db_session).save(CandidateProfile(full_name="Jane Doe"))
    documents = DocumentRepo(db_session)
    template = documents.get_or_create_template(
        kind="resume", name="resume", file_path="cv/resume.tex.jinja"
    )
    extracted_text_path = tmp_path / "resume.extracted.txt"
    extracted_text_path.write_text(
        "Jane Doe\nBackend Engineer, Acme\n"
        "Built APIs serving 1M requests/day using Python and AWS\n",
        encoding="utf-8",
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
    match_score = MatchRepo(db_session).save(
        MatchScore(
            job_posting_id=posting.id, profile_id=profile.id, score=80.0, rationale="Good fit."
        )
    )
    application = ApplicationRepo(db_session).create(
        Application(job_posting_id=posting.id, resume_version_id=resume_version.id)
    )
    return application, posting, resume_version, match_score


_QUESTIONS = InterviewPrepExtraction(
    questions=[
        InterviewQuestionDraft(
            category=QuestionCategory.TECHNICAL,
            question="Tell me about a time you scaled a backend system.",
            suggested_talking_points=["Built APIs serving 1M requests/day using Python and AWS"],
        )
    ]
)


def test_run_generates_and_persists_questions(
    db_session: Session, tmp_path: Path, fake_llm_factory: FakeLLMFactory
) -> None:
    """Happy path: questions generated and persisted via InterviewRepo."""
    application, posting, resume_version, match_score = _seed(
        db_session,
        tmp_path,
        posting_text=(
            "We are hiring a Backend Engineer to build APIs and scale our "
            "distributed systems using Python and AWS across a growing platform team. "
            "You will own service reliability, mentor junior engineers, and partner "
            "closely with the observability and infrastructure teams on rollout plans."
        ),
    )
    ctx = _make_context(db_session, fake_llm_factory(_QUESTIONS))
    agent = InterviewPrepAgent()

    result = agent.run(
        InterviewPrepInput(
            application=application,
            job_posting=posting,
            resume_version=resume_version,
            match_score=match_score,
            interview_type=InterviewType.TECHNICAL,
        ),
        ctx,
    )

    assert result.output.interview.id is not None
    assert len(result.output.questions) == 1
    assert result.warnings == []
    fetched = ctx.repos.interviews.list_questions(result.output.interview.id)
    assert len(fetched) == 1


def test_run_warns_on_short_posting_text(
    db_session: Session, tmp_path: Path, fake_llm_factory: FakeLLMFactory
) -> None:
    """agents.md §10 Failure handling: thin grounding data surfaces a warning."""
    application, posting, resume_version, match_score = _seed(
        db_session, tmp_path, posting_text="Backend role."
    )
    ctx = _make_context(db_session, fake_llm_factory(_QUESTIONS))
    agent = InterviewPrepAgent()

    result = agent.run(
        InterviewPrepInput(
            application=application,
            job_posting=posting,
            resume_version=resume_version,
            match_score=match_score,
            interview_type=InterviewType.PHONE_SCREEN,
        ),
        ctx,
    )

    assert any("less-grounded" in warning for warning in result.warnings)


def test_run_raises_on_unpersisted_application(
    db_session: Session, tmp_path: Path, fake_llm_factory: FakeLLMFactory
) -> None:
    _application, posting, resume_version, match_score = _seed(
        db_session, tmp_path, posting_text="Backend role."
    )
    ctx = _make_context(db_session, fake_llm_factory(_QUESTIONS))
    agent = InterviewPrepAgent()
    unsaved_application = Application(job_posting_id=posting.id)

    with pytest.raises(ValueError, match="already-persisted"):
        agent.run(
            InterviewPrepInput(
                application=unsaved_application,
                job_posting=posting,
                resume_version=resume_version,
                match_score=match_score,
                interview_type=InterviewType.PHONE_SCREEN,
            ),
            ctx,
        )


def test_run_raises_when_match_score_belongs_to_different_posting(
    db_session: Session, tmp_path: Path, fake_llm_factory: FakeLLMFactory
) -> None:
    application, posting, resume_version, _match_score = _seed(
        db_session, tmp_path, posting_text="Backend role."
    )
    other_posting = JobRepo(db_session).save(
        JobPosting(source="greenhouse", source_id="2", title="Other", url="https://example.com/2")
    )
    mismatched_score = MatchRepo(db_session).save(
        MatchScore(
            job_posting_id=other_posting.id,
            profile_id=resume_version.profile_id,
            score=50.0,
            rationale="Different posting.",
        )
    )
    ctx = _make_context(db_session, fake_llm_factory(_QUESTIONS))
    agent = InterviewPrepAgent()

    with pytest.raises(ValueError, match="job_posting_id"):
        agent.run(
            InterviewPrepInput(
                application=application,
                job_posting=posting,
                resume_version=resume_version,
                match_score=mismatched_score,
                interview_type=InterviewType.PHONE_SCREEN,
            ),
            ctx,
        )
