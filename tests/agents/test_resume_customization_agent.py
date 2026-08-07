"""Tests for the Resume Customization Agent (tasks.md T11.3, phases.md Phase 11).

Uses a small scripted fake LLM (not the shared ``FakeLLMProvider``,
which only ever returns one fixed response -- this agent needs an
ordered sequence of draft/review responses to exercise the
drafter->reviewer loop). Real LaTeX compilation and pdftotext
verification run for real throughout (same rationale as
tests/documents/test_renderer.py).
"""

from pathlib import Path
from typing import ClassVar

import pytest
from sqlalchemy.orm import Session

from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.agents.resume_customization_agent import (
    ResumeCustomizationAgent,
    ResumeCustomizationInput,
    _build_render_context,
)
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
from jobhunt_core.errors import RenderError
from jobhunt_core.llm.types import StructuredLLMResponse
from jobhunt_core.schemas.ats import ATSReport
from jobhunt_core.schemas.document import ResumeDraft, ReviewVerdict, TailoredExperienceEntry
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.profile import CandidateProfile, EducationEntry, ExperienceEntry
from jobhunt_core.storage.repositories import (
    ApplicationRepo,
    ATSRepo,
    DocumentRepo,
    InterviewRepo,
    JobRepo,
    MatchRepo,
    ProfileRepo,
)


class _ScriptedLLM:
    """Returns an ordered sequence of (schema, parsed_value) pairs, one per call."""

    name: ClassVar[str] = "scripted"

    def __init__(self, responses: list[tuple[type, object]]) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []

    def complete(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("ResumeCustomizationAgent should never call complete()")

    def complete_structured(self, prompt, *, model, response_schema, temperature=0.0):  # type: ignore[no-untyped-def]
        self.prompts.append(prompt)
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


def _profile(**overrides: object) -> CandidateProfile:
    defaults: dict = dict(
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
                bullets=["Built APIs serving 1M requests/day"],
            )
        ],
        education=[EducationEntry(institution="State University", degree="B.S.")],
    )
    defaults.update(overrides)
    return CandidateProfile(**defaults)


def _posting(**overrides: object) -> JobPosting:
    defaults: dict = dict(
        source="greenhouse",
        source_id="1",
        title="Backend Engineer",
        url="https://example.com/jobs/1",
        normalized_description="Need a Python and AWS backend engineer.",
    )
    defaults.update(overrides)
    return JobPosting(**defaults)


_APPROVED_DRAFT = ResumeDraft(
    summary="Backend engineer skilled in Python and AWS.",
    skills=["Python", "AWS"],
    experience=[
        TailoredExperienceEntry(
            title="Backend Engineer",
            company="Acme",
            start_date="2021",
            end_date="Present",
            bullets=["Built APIs serving 1M requests/day"],
        )
    ],
    certifications=[],
)
_APPROVAL = ReviewVerdict(approved=True, feedback="Looks good.", fabrication_flags=[])


def _make_context(db_session: Session, llm: object, data_dir: Path) -> RunContext:
    settings = Settings(
        llm=LLMConfig(default_provider="fake", providers={}),
        agents={
            "resume_customization": AgentConfig(enabled=True, provider="fake", model="fake-model")
        },
        sources={},
        data_dir=data_dir,
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


def _persist(db_session: Session, profile: CandidateProfile, posting: JobPosting):
    saved_profile = ProfileRepo(db_session).save(profile)
    saved_posting = JobRepo(db_session).save(posting)
    ats_report = ATSReport(job_posting_id=saved_posting.id, profile_id=saved_profile.id)
    return saved_profile, saved_posting, ats_report


def test_run_approved_first_try_renders_compiles_and_persists(
    db_session: Session, tmp_path: Path
) -> None:
    """The happy path: approved on the first review, no redraft, real PDF produced."""
    llm = _ScriptedLLM([(ResumeDraft, _APPROVED_DRAFT), (ReviewVerdict, _APPROVAL)])
    ctx = _make_context(db_session, llm, tmp_path)
    profile, posting, ats_report = _persist(db_session, _profile(), _posting())
    agent = ResumeCustomizationAgent()

    result = agent.run(
        ResumeCustomizationInput(
            candidate_profile=profile, job_posting=posting, ats_report=ats_report
        ),
        ctx,
    )

    assert Path(result.output.rendered_pdf_path).exists()
    assert result.output.ats_verification_passed is True
    assert result.warnings == []
    assert result.output.profile_id == profile.id
    assert result.output.job_posting_id == posting.id


def test_run_persists_resume_version_via_repository(db_session: Session, tmp_path: Path) -> None:
    """The output round-trips through DocumentRepo."""
    llm = _ScriptedLLM([(ResumeDraft, _APPROVED_DRAFT), (ReviewVerdict, _APPROVAL)])
    ctx = _make_context(db_session, llm, tmp_path)
    profile, posting, ats_report = _persist(db_session, _profile(), _posting())
    agent = ResumeCustomizationAgent()

    result = agent.run(
        ResumeCustomizationInput(
            candidate_profile=profile, job_posting=posting, ats_report=ats_report
        ),
        ctx,
    )

    fetched = ctx.repos.documents.get_resume_version(result.output.id)
    assert fetched is not None
    assert fetched.rendered_pdf_path == result.output.rendered_pdf_path


def test_run_rejected_then_redraft_approved_succeeds_with_warning(
    db_session: Session, tmp_path: Path
) -> None:
    """agents.md §6: one automatic redraft on rejection, then success."""
    rejection = ReviewVerdict(
        approved=False,
        feedback="The 'led a team of 20' claim isn't in the profile.",
        fabrication_flags=["led a team of 20"],
    )
    llm = _ScriptedLLM(
        [
            (ResumeDraft, _APPROVED_DRAFT),
            (ReviewVerdict, rejection),
            (ResumeDraft, _APPROVED_DRAFT),
            (ReviewVerdict, _APPROVAL),
        ]
    )
    ctx = _make_context(db_session, llm, tmp_path)
    profile, posting, ats_report = _persist(db_session, _profile(), _posting())
    agent = ResumeCustomizationAgent()

    result = agent.run(
        ResumeCustomizationInput(
            candidate_profile=profile, job_posting=posting, ats_report=ats_report
        ),
        ctx,
    )

    assert Path(result.output.rendered_pdf_path).exists()
    assert any("redrafted 1 time" in warning for warning in result.warnings)
    # The redraft prompt must actually carry the reviewer's feedback forward.
    assert "led a team of 20" in llm.prompts[2]


def test_run_rejected_twice_raises_and_persists_nothing(
    db_session: Session, tmp_path: Path
) -> None:
    """tasks.md T11.3 fixture test: a fabrication that survives redraft never ships.

    Two rejections in a row (initial + the one automatic redraft) must
    raise RenderError rather than silently rendering/persisting the
    still-rejected draft -- the reviewer gate is what actually
    enforces rules.md AI Coding Rule 1 here, so this proves the agent
    obeys a REJECT verdict rather than proceeding anyway.
    """
    rejection = ReviewVerdict(
        approved=False,
        feedback="Still contains an unsupported 'AWS certified' claim.",
        fabrication_flags=["AWS certified"],
    )
    llm = _ScriptedLLM(
        [
            (ResumeDraft, _APPROVED_DRAFT),
            (ReviewVerdict, rejection),
            (ResumeDraft, _APPROVED_DRAFT),
            (ReviewVerdict, rejection),
        ]
    )
    ctx = _make_context(db_session, llm, tmp_path)
    profile, posting, ats_report = _persist(db_session, _profile(), _posting())
    agent = ResumeCustomizationAgent()

    with pytest.raises(RenderError, match="rejected"):
        agent.run(
            ResumeCustomizationInput(
                candidate_profile=profile, job_posting=posting, ats_report=ats_report
            ),
            ctx,
        )

    assert ctx.repos.documents.list_resume_versions(profile_id=profile.id) == []


def test_run_raises_on_unpersisted_posting(db_session: Session, tmp_path: Path) -> None:
    """Failure-path test: a posting with id=None is rejected before any LLM call."""
    llm = _ScriptedLLM([])  # no calls expected
    ctx = _make_context(db_session, llm, tmp_path)
    profile, posting, ats_report = _persist(db_session, _profile(), _posting())
    unsaved_posting = posting.model_copy(update={"id": None})
    agent = ResumeCustomizationAgent()

    with pytest.raises(ValueError, match="already-persisted"):
        agent.run(
            ResumeCustomizationInput(
                candidate_profile=profile, job_posting=unsaved_posting, ats_report=ats_report
            ),
            ctx,
        )


def test_run_handles_special_characters_without_breaking_compilation(
    db_session: Session, tmp_path: Path
) -> None:
    """phases.md Phase 11 AC: special LaTeX characters anywhere in the content still compile."""
    dangerous_draft = ResumeDraft(
        summary="Cut costs by 20% at AT&T using C# and user_id #normalization.",
        skills=["C#", "AT&T systems"],
        experience=[
            TailoredExperienceEntry(
                title="Engineer",
                company="AT&T",
                start_date="2021",
                end_date="Present",
                bullets=["Reduced spend by 20% via user_id #dedup & caching"],
            )
        ],
        certifications=[],
    )
    llm = _ScriptedLLM([(ResumeDraft, dangerous_draft), (ReviewVerdict, _APPROVAL)])
    ctx = _make_context(db_session, llm, tmp_path)
    profile, posting, ats_report = _persist(db_session, _profile(), _posting())
    agent = ResumeCustomizationAgent()

    result = agent.run(
        ResumeCustomizationInput(
            candidate_profile=profile, job_posting=posting, ats_report=ats_report
        ),
        ctx,
    )

    assert Path(result.output.rendered_pdf_path).exists()
    assert result.output.ats_verification_passed is True


def test_build_render_context_never_lets_draft_touch_contact_or_education() -> None:
    """Structural guarantee: ResumeDraft has no name/contact/education fields at all."""
    profile = _profile()

    context = _build_render_context(profile, _APPROVED_DRAFT)

    assert context["full_name"] == "Jane Doe"
    assert context["email"] == "jane@example.com"
    assert context["education"] == [e.model_dump() for e in profile.education]
    assert not hasattr(_APPROVED_DRAFT, "education")
    assert not hasattr(_APPROVED_DRAFT, "full_name")
