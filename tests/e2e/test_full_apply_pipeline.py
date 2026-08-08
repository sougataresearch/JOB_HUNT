"""End-to-end fixture pipeline test (tasks.md T17.1, testing.md §6).

Runs Resume Analysis -> Job Matching -> ATS Optimization -> Resume
Customization -> Cover Letter -> Email Generation -> Application
Tracking against fixture CV + fixture posting content, entirely
offline: a single scripted fake LLM provider for every agent involved
(never a live call), plus real LaTeX compiles for the two
document-rendering agents -- same rationale as
tests/documents/test_renderer.py: proving "generated PDFs exist on
disk and pass ATS text verification" (testing.md §6) needs a real
compile, not a mock.

Job Search Agent itself (multi-source fetching + dedup) is out of
scope here: every other agent-level test in this codebase already
starts from an already-persisted ``JobPosting``, and this test does
the same rather than re-deriving Job Search's own already-tested
behavior. Interview Prep and Career Analytics are likewise not run
here -- testing.md §6's own description of this test's scope is
"Resume Analysis -> ... -> Application Tracking," and both of those
two agents are consumers of an *existing* Application, not part of
producing the first one.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from sqlalchemy.orm import Session

from jobhunt_core.agents.application_tracking_agent import (
    ApplicationTrackingAgent,
    ApplicationTrackingInput,
)
from jobhunt_core.agents.ats_optimization_agent import ATSOptimizationAgent, ATSOptimizationInput
from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.agents.cover_letter_agent import CoverLetterAgent, CoverLetterInput
from jobhunt_core.agents.email_generation_agent import EmailGenerationAgent, EmailGenerationInput
from jobhunt_core.agents.job_matching_agent import JobMatchingAgent, JobMatchingInput
from jobhunt_core.agents.resume_analysis_agent import ResumeAnalysisAgent, ResumeAnalysisInput
from jobhunt_core.agents.resume_customization_agent import (
    ResumeCustomizationAgent,
    ResumeCustomizationInput,
)
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
from jobhunt_core.llm.types import StructuredLLMResponse
from jobhunt_core.schemas.application import ApplicationStatus
from jobhunt_core.schemas.ats import ATSGapClassification
from jobhunt_core.schemas.document import (
    CoverLetterDraft,
    ResumeDraft,
    ReviewVerdict,
    TailoredExperienceEntry,
)
from jobhunt_core.schemas.email import EmailDraftExtraction
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.match import MatchScoreExtraction
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

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "cvs"

_PIPELINE_AGENTS = (
    "resume_analysis",
    "job_matching",
    "ats_optimization",
    "resume_customization",
    "cover_letter",
    "email_generation",
)


class _ScriptedLLM:
    """Returns an ordered sequence of (schema, parsed_value) pairs, one per call.

    Same small fake already used in test_resume_customization_agent.py/
    test_cover_letter_agent.py -- this test threads it across many more
    agent types in one continuous run instead of one agent's own
    draft/review loop.
    """

    name: ClassVar[str] = "scripted"

    def __init__(self, responses: list[tuple[type, object]]) -> None:
        self._responses = list(responses)

    def complete(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("No agent in this pipeline should call complete()")

    def complete_structured(self, prompt, *, model, response_schema, temperature=0.0):  # type: ignore[no-untyped-def]
        expected_schema, parsed = self._responses.pop(0)
        assert (
            response_schema is expected_schema
        ), f"expected a {expected_schema.__name__} call, got {response_schema.__name__}"
        return StructuredLLMResponse(
            text="fake",
            parsed=parsed,
            tokens_in=1,
            tokens_out=1,
            cost_estimate_usd=0.0,
            latency_ms=1,
        )


_CANDIDATE_EXTRACTION = CandidateProfileExtraction(
    full_name="Jane Doe",
    email="jane@example.com",
    phone="555-1234",
    location="Seattle, WA",
    skills=["Python", "AWS"],
    experience=[
        ExperienceEntry(
            title="Backend Engineer",
            company="Acme",
            start_date="2021",
            end_date="Present",
            bullets=["Built APIs serving 1M requests/day using Python and AWS"],
        )
    ],
)
_MATCH_EXTRACTION = MatchScoreExtraction(
    score=82.0,
    matched_requirements=["Python", "AWS"],
    missing_requirements=["Kubernetes"],
    rationale="Strong overlap on Python and AWS experience; no Kubernetes experience found.",
)
# The deterministic keyword-gap step should find exactly "Kubernetes"
# missing (Python/AWS/Backend/Engineer/APIs all appear in the profile
# text too) -- classified unsupported since it genuinely isn't backed
# by the candidate's real experience (rules.md AI Coding Rule 1).
_ATS_CLASSIFICATION = ATSGapClassification(unsupported_gaps=["Kubernetes"])
_RESUME_DRAFT = ResumeDraft(
    summary="Backend engineer skilled in Python and AWS.",
    skills=["Python", "AWS"],
    experience=[
        TailoredExperienceEntry(
            title="Backend Engineer",
            company="Acme",
            start_date="2021",
            end_date="Present",
            bullets=["Built APIs serving 1M requests/day using Python and AWS"],
        )
    ],
)
_APPROVAL = ReviewVerdict(approved=True, feedback="Looks good.", fabrication_flags=[])
_COVER_LETTER_DRAFT = CoverLetterDraft(
    salutation="Dear Hiring Manager,",
    paragraphs=[
        "I'm excited to apply for the Backend Engineer role on your Platform team.",
        "In my current role at Acme I built APIs serving 1M requests/day using Python and "
        "AWS, directly relevant to your distributed systems work.",
    ],
    sign_off="Sincerely,",
)
_EMAIL_EXTRACTION = EmailDraftExtraction(
    to=None,
    subject="Application for Backend Engineer",
    body="Please see my attached resume and cover letter.",
)


def _make_context(db_session: Session, llm: object, tmp_path: Path) -> RunContext:
    settings = Settings(
        llm=LLMConfig(default_provider="fake", providers={}),
        agents={
            name: AgentConfig(enabled=True, provider="fake", model="fake-model")
            for name in _PIPELINE_AGENTS
        },
        sources={},
        data_dir=tmp_path,
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


def test_full_apply_pipeline_produces_application_with_verified_documents(
    db_session: Session, tmp_path: Path
) -> None:
    """Resume Analysis -> ... -> Application Tracking, no live network/LLM calls (testing.md §6)."""
    llm = _ScriptedLLM(
        [
            (CandidateProfileExtraction, _CANDIDATE_EXTRACTION),
            (MatchScoreExtraction, _MATCH_EXTRACTION),
            (ATSGapClassification, _ATS_CLASSIFICATION),
            (ResumeDraft, _RESUME_DRAFT),
            (ReviewVerdict, _APPROVAL),
            (CoverLetterDraft, _COVER_LETTER_DRAFT),
            (ReviewVerdict, _APPROVAL),
            (EmailDraftExtraction, _EMAIL_EXTRACTION),
        ]
    )
    ctx = _make_context(db_session, llm, tmp_path)

    # 1. Resume Analysis: fixture CV file -> CandidateProfile.
    resume_analysis_result = ResumeAnalysisAgent().run(
        ResumeAnalysisInput(cv_file_path=FIXTURES_DIR / "jane_doe_complete.md"), ctx
    )
    profile = ctx.repos.profiles.save(resume_analysis_result.output)
    assert profile.full_name == "Jane Doe"

    # 2. A posting is already sourced (Job Search Agent out of scope here).
    posting = ctx.repos.jobs.save(
        JobPosting(
            source="greenhouse",
            source_id="1",
            title="Backend Engineer",
            url="https://example.com/jobs/1",
            normalized_description=(
                "We are hiring a Backend Engineer to build APIs and scale our "
                "distributed systems using Python, AWS, and Kubernetes."
            ),
        )
    )

    # 3. Job Matching.
    match_result = JobMatchingAgent().run(
        JobMatchingInput(candidate_profile=profile, job_posting=posting), ctx
    )
    match_score = ctx.repos.matches.save(match_result.output)
    assert match_score.rationale.strip()

    # 4. ATS Optimization.
    ats_result = ATSOptimizationAgent().run(
        ATSOptimizationInput(candidate_profile=profile, job_posting=posting), ctx
    )
    ats_report = ctx.repos.ats.save(ats_result.output)
    assert "Kubernetes" in ats_report.unsupported_gaps

    # 5. Resume Customization -- real LaTeX compile.
    resume_version = (
        ResumeCustomizationAgent()
        .run(
            ResumeCustomizationInput(
                candidate_profile=profile, job_posting=posting, ats_report=ats_report
            ),
            ctx,
        )
        .output
    )
    assert Path(resume_version.rendered_pdf_path).exists()
    assert resume_version.ats_verification_passed is True

    # 6. Cover Letter -- real LaTeX compile.
    cover_letter = (
        CoverLetterAgent()
        .run(
            CoverLetterInput(
                candidate_profile=profile, job_posting=posting, resume_version=resume_version
            ),
            ctx,
        )
        .output
    )
    assert Path(cover_letter.rendered_pdf_path).exists()

    # 7. Email Generation.
    email_draft = (
        EmailGenerationAgent()
        .run(
            EmailGenerationInput(
                job_posting=posting, resume_version=resume_version, cover_letter=cover_letter
            ),
            ctx,
        )
        .output
    )
    assert email_draft.status == "draft"
    assert Path(resume_version.rendered_pdf_path) in email_draft.attachments
    assert Path(cover_letter.rendered_pdf_path) in email_draft.attachments

    # 8. Application Tracking -- deterministic, no LLM call (the
    # scripted queue is already exhausted; any attempted call would
    # raise IndexError immediately, itself a loud failure).
    application = (
        ApplicationTrackingAgent()
        .run(
            ApplicationTrackingInput(
                job_posting=posting,
                resume_version=resume_version,
                cover_letter=cover_letter,
                status=ApplicationStatus.SUBMITTED,
            ),
            ctx,
        )
        .output
    )

    assert application.job_posting_id == posting.id
    assert application.resume_version_id == resume_version.id
    assert application.cover_letter_id == cover_letter.id
    assert application.status == ApplicationStatus.SUBMITTED

    fetched = ctx.repos.applications.get(application.id)
    assert fetched is not None
    assert fetched.resume_version_id == resume_version.id
    assert fetched.cover_letter_id == cover_letter.id
