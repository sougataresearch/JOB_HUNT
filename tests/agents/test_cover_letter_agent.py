"""Tests for the Cover Letter Agent (tasks.md T12.2, phases.md Phase 12).

Uses the same small scripted fake LLM pattern as
test_resume_customization_agent.py (an ordered sequence of draft/review
responses). Real LaTeX compilation runs throughout (same rationale as
tests/documents/test_renderer.py).
"""

from pathlib import Path
from typing import ClassVar

import pytest
from sqlalchemy.orm import Session

from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.agents.cover_letter_agent import (
    CoverLetterAgent,
    CoverLetterInput,
    _count_referenced_details,
    _posting_detail_words,
)
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
from jobhunt_core.errors import RenderError
from jobhunt_core.llm.types import StructuredLLMResponse
from jobhunt_core.schemas.document import CoverLetterDraft, ResumeVersion, ReviewVerdict
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
        raise AssertionError("CoverLetterAgent should never call complete()")

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
        normalized_description=(
            "We are hiring a Backend Engineer to join our Platform team, "
            "working on distributed systems and Kubernetes infrastructure "
            "to support our observability mission."
        ),
    )
    defaults.update(overrides)
    return JobPosting(**defaults)


_APPROVED_DRAFT = CoverLetterDraft(
    salutation="Dear Hiring Manager,",
    paragraphs=[
        "I'm excited to apply for the Backend Engineer role on your Platform team.",
        "In my current role at Acme I built APIs serving 1M requests/day, directly "
        "relevant to the distributed systems and Kubernetes infrastructure work "
        "your observability mission depends on.",
    ],
    sign_off="Sincerely,",
)
_GENERIC_DRAFT = CoverLetterDraft(
    salutation="Dear Hiring Manager,",
    paragraphs=["I would love to work at your company and think I would be a great fit."],
    sign_off="Sincerely,",
)
_APPROVAL = ReviewVerdict(approved=True, feedback="Looks good.", fabrication_flags=[])


def _make_context(db_session: Session, llm: object, data_dir: Path) -> RunContext:
    settings = Settings(
        llm=LLMConfig(default_provider="fake", providers={}),
        agents={"cover_letter": AgentConfig(enabled=True, provider="fake", model="fake-model")},
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


def _persist(
    db_session: Session, profile: CandidateProfile, posting: JobPosting, tmp_path: Path
) -> tuple[CandidateProfile, JobPosting, ResumeVersion]:
    """Persist a profile, posting, and a fake-but-real ResumeVersion pointing at a real file.

    ``ats_extracted_text_path`` must point at a real, readable file --
    CoverLetterAgent reads it directly (agents.md §7's reuse of Phase
    11's PDF-verification artifact), so a fixture value would break at
    the first ``Path.read_text()`` call.
    """
    saved_profile = ProfileRepo(db_session).save(profile)
    saved_posting = JobRepo(db_session).save(posting)
    documents = DocumentRepo(db_session)
    template = documents.get_or_create_template(
        kind="resume", name="resume", file_path="cv/resume.tex.jinja"
    )
    extracted_text_path = tmp_path / "resume.extracted.txt"
    extracted_text_path.write_text(
        "Jane Doe\nBackend Engineer, Acme\nBuilt APIs serving 1M requests/day\n",
        encoding="utf-8",
    )
    resume_version = documents.save_resume_version(
        ResumeVersion(
            profile_id=saved_profile.id,
            job_posting_id=saved_posting.id,
            template_id=template.id or "",
            rendered_pdf_path=str(tmp_path / "resume.pdf"),
            rendered_tex_path=str(tmp_path / "resume.tex"),
            ats_verification_passed=True,
            ats_extracted_text_path=str(extracted_text_path),
        )
    )
    return saved_profile, saved_posting, resume_version


def test_run_approved_first_try_renders_compiles_and_persists(
    db_session: Session, tmp_path: Path
) -> None:
    """The happy path: approved on the first review, no redraft, real PDF produced."""
    llm = _ScriptedLLM([(CoverLetterDraft, _APPROVED_DRAFT), (ReviewVerdict, _APPROVAL)])
    ctx = _make_context(db_session, llm, tmp_path)
    profile, posting, resume_version = _persist(db_session, _profile(), _posting(), tmp_path)
    agent = CoverLetterAgent()

    result = agent.run(
        CoverLetterInput(
            candidate_profile=profile, job_posting=posting, resume_version=resume_version
        ),
        ctx,
    )

    assert Path(result.output.rendered_pdf_path).exists()
    assert result.output.job_posting_id == posting.id
    assert result.output.resume_version_id == resume_version.id
    assert result.warnings == []


def test_run_persists_cover_letter_via_repository(db_session: Session, tmp_path: Path) -> None:
    """The output round-trips through DocumentRepo."""
    llm = _ScriptedLLM([(CoverLetterDraft, _APPROVED_DRAFT), (ReviewVerdict, _APPROVAL)])
    ctx = _make_context(db_session, llm, tmp_path)
    profile, posting, resume_version = _persist(db_session, _profile(), _posting(), tmp_path)
    agent = CoverLetterAgent()

    result = agent.run(
        CoverLetterInput(
            candidate_profile=profile, job_posting=posting, resume_version=resume_version
        ),
        ctx,
    )

    fetched = ctx.repos.documents.get_cover_letter(result.output.id)
    assert fetched is not None
    assert fetched.rendered_pdf_path == result.output.rendered_pdf_path


def test_run_rejected_then_redraft_approved_succeeds_with_warning(
    db_session: Session, tmp_path: Path
) -> None:
    """agents.md §7: same one-automatic-redraft-on-rejection pattern as Resume Customization."""
    rejection = ReviewVerdict(
        approved=False,
        feedback="This contradicts the resume -- no team lead claim is supported.",
        fabrication_flags=["team lead"],
    )
    llm = _ScriptedLLM(
        [
            (CoverLetterDraft, _APPROVED_DRAFT),
            (ReviewVerdict, rejection),
            (CoverLetterDraft, _APPROVED_DRAFT),
            (ReviewVerdict, _APPROVAL),
        ]
    )
    ctx = _make_context(db_session, llm, tmp_path)
    profile, posting, resume_version = _persist(db_session, _profile(), _posting(), tmp_path)
    agent = CoverLetterAgent()

    result = agent.run(
        CoverLetterInput(
            candidate_profile=profile, job_posting=posting, resume_version=resume_version
        ),
        ctx,
    )

    assert Path(result.output.rendered_pdf_path).exists()
    assert any("redrafted 1 time" in warning for warning in result.warnings)
    assert "team lead" in llm.prompts[2]


def test_run_rejected_twice_raises_and_persists_nothing(
    db_session: Session, tmp_path: Path
) -> None:
    """A fabrication/contradiction that survives redraft never ships (rules.md AI Coding Rule 1)."""
    rejection = ReviewVerdict(
        approved=False,
        feedback="Still contradicts the resume's claims.",
        fabrication_flags=["managed a team of 5"],
    )
    llm = _ScriptedLLM(
        [
            (CoverLetterDraft, _APPROVED_DRAFT),
            (ReviewVerdict, rejection),
            (CoverLetterDraft, _APPROVED_DRAFT),
            (ReviewVerdict, rejection),
        ]
    )
    ctx = _make_context(db_session, llm, tmp_path)
    profile, posting, resume_version = _persist(db_session, _profile(), _posting(), tmp_path)
    agent = CoverLetterAgent()

    with pytest.raises(RenderError, match="rejected"):
        agent.run(
            CoverLetterInput(
                candidate_profile=profile, job_posting=posting, resume_version=resume_version
            ),
            ctx,
        )

    assert ctx.repos.documents.list_cover_letters(job_posting_id=posting.id) == []


def test_run_raises_on_unpersisted_posting(db_session: Session, tmp_path: Path) -> None:
    """Failure-path test: a posting with id=None is rejected before any LLM call."""
    llm = _ScriptedLLM([])  # no calls expected
    ctx = _make_context(db_session, llm, tmp_path)
    profile, posting, resume_version = _persist(db_session, _profile(), _posting(), tmp_path)
    unsaved_posting = posting.model_copy(update={"id": None})
    agent = CoverLetterAgent()

    with pytest.raises(ValueError, match="already-persisted"):
        agent.run(
            CoverLetterInput(
                candidate_profile=profile,
                job_posting=unsaved_posting,
                resume_version=resume_version,
            ),
            ctx,
        )


def test_run_raises_when_resume_version_belongs_to_different_profile(
    db_session: Session, tmp_path: Path
) -> None:
    """A ResumeVersion for a different profile must never be silently accepted."""
    llm = _ScriptedLLM([])  # no calls expected
    ctx = _make_context(db_session, llm, tmp_path)
    _profile_a, posting, resume_version = _persist(db_session, _profile(), _posting(), tmp_path)
    other_profile = ProfileRepo(db_session).save(_profile(full_name="Someone Else"))
    agent = CoverLetterAgent()

    with pytest.raises(ValueError, match="profile_id"):
        agent.run(
            CoverLetterInput(
                candidate_profile=other_profile, job_posting=posting, resume_version=resume_version
            ),
            ctx,
        )


def test_run_handles_special_characters_without_breaking_compilation(
    db_session: Session, tmp_path: Path
) -> None:
    """phases.md Phase 11 AC (shared renderer): special LaTeX characters still compile."""
    dangerous_draft = CoverLetterDraft(
        salutation="Dear Hiring Manager,",
        paragraphs=["I saved 20% at AT&T using C# and reduced spend via user_id #dedup & caching."],
        sign_off="Sincerely,",
    )
    llm = _ScriptedLLM([(CoverLetterDraft, dangerous_draft), (ReviewVerdict, _APPROVAL)])
    ctx = _make_context(db_session, llm, tmp_path)
    profile, posting, resume_version = _persist(db_session, _profile(), _posting(), tmp_path)
    agent = CoverLetterAgent()

    result = agent.run(
        CoverLetterInput(
            candidate_profile=profile, job_posting=posting, resume_version=resume_version
        ),
        ctx,
    )

    assert Path(result.output.rendered_pdf_path).exists()


def test_run_warns_when_letter_reads_as_generic(db_session: Session, tmp_path: Path) -> None:
    """phases.md Phase 12 AC: a letter referencing few posting details is flagged, not blocked."""
    llm = _ScriptedLLM([(CoverLetterDraft, _GENERIC_DRAFT), (ReviewVerdict, _APPROVAL)])
    ctx = _make_context(db_session, llm, tmp_path)
    profile, posting, resume_version = _persist(db_session, _profile(), _posting(), tmp_path)
    agent = CoverLetterAgent()

    result = agent.run(
        CoverLetterInput(
            candidate_profile=profile, job_posting=posting, resume_version=resume_version
        ),
        ctx,
    )

    assert Path(result.output.rendered_pdf_path).exists()
    assert any("concrete posting detail" in warning for warning in result.warnings)


def test_posting_detail_words_and_count_are_deterministic() -> None:
    """Unit-level check of the keyword-presence eval helpers (no LLM/compile needed)."""
    posting = _posting()

    words = _posting_detail_words(posting)

    assert "kubernetes" in words
    assert "platform" in words
    assert "with" not in words  # stopword
    assert _count_referenced_details("I know Kubernetes and the Platform team.", words) >= 2
    assert _count_referenced_details("Generic text with no overlap at all.", words) == 0
