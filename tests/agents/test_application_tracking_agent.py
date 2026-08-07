"""Tests for the Application Tracking Agent (tasks.md T14.2, phases.md Phase 14).

No LLM call at all (agents.md §9 Prompt template: None) -- every test
uses a real repo-backed ``RunContext`` with no ``LLMProvider`` faking
needed at all beyond a placeholder that must never be called.
"""

from typing import ClassVar

import pytest
from sqlalchemy.orm import Session

from jobhunt_core.agents.application_tracking_agent import (
    ApplicationTrackingAgent,
    ApplicationTrackingInput,
    export_applications_csv,
)
from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.config.settings import LLMConfig, Settings
from jobhunt_core.schemas.application import Application, ApplicationStatus
from jobhunt_core.schemas.document import ResumeVersion
from jobhunt_core.schemas.job import JobPosting
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


class _NeverCallLLM:
    """Fails the test loudly if the agent ever calls the LLM (it never should)."""

    name: ClassVar[str] = "never"

    def complete(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("ApplicationTrackingAgent should never call the LLM")

    def complete_structured(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("ApplicationTrackingAgent should never call the LLM")


def _make_context(db_session: Session) -> RunContext:
    settings = Settings(llm=LLMConfig(default_provider="fake", providers={}), agents={}, sources={})
    repos = RepositoryBundle(
        profiles=ProfileRepo(db_session),
        jobs=JobRepo(db_session),
        matches=MatchRepo(db_session),
        ats=ATSRepo(db_session),
        applications=ApplicationRepo(db_session),
        interviews=InterviewRepo(db_session),
        documents=DocumentRepo(db_session),
    )
    return RunContext(settings=settings, llm=_NeverCallLLM(), repos=repos)  # type: ignore[arg-type]


def _posting(db_session: Session, **overrides: object) -> JobPosting:
    defaults: dict = dict(
        source="greenhouse", source_id="1", title="Engineer", url="https://example.com/1"
    )
    defaults.update(overrides)
    return JobRepo(db_session).save(JobPosting(**defaults))


def _resume_version(db_session: Session, job_posting_id: str) -> ResumeVersion:
    documents = DocumentRepo(db_session)
    template = documents.get_or_create_template(
        kind="resume", name="resume", file_path="cv/resume.tex.jinja"
    )
    profile = ProfileRepo(db_session).save(CandidateProfile(full_name="Jane Doe"))
    return documents.save_resume_version(
        ResumeVersion(
            profile_id=profile.id,
            job_posting_id=job_posting_id,
            template_id=template.id or "",
            rendered_pdf_path="r.pdf",
            rendered_tex_path="r.tex",
            ats_verification_passed=True,
            ats_extracted_text_path="r.txt",
        )
    )


def test_run_creates_application_from_approved_package(db_session: Session) -> None:
    """Create mode: no prior application, resume/cover_letter references persisted."""
    ctx = _make_context(db_session)
    posting = _posting(db_session)
    resume_version = _resume_version(db_session, posting.id)
    agent = ApplicationTrackingAgent()

    result = agent.run(
        ApplicationTrackingInput(job_posting=posting, resume_version=resume_version), ctx
    )

    assert result.output.job_posting_id == posting.id
    assert result.output.resume_version_id == resume_version.id
    assert result.output.status == ApplicationStatus.DRAFTED
    assert result.warnings == []


def test_run_is_idempotent_for_duplicate_creation(db_session: Session) -> None:
    """agents.md §9 Failure handling: a second create call returns the existing record."""
    ctx = _make_context(db_session)
    posting = _posting(db_session)
    agent = ApplicationTrackingAgent()

    first = agent.run(ApplicationTrackingInput(job_posting=posting), ctx)
    second = agent.run(ApplicationTrackingInput(job_posting=posting), ctx)

    assert first.output.id == second.output.id
    assert len(ctx.repos.applications.list_events(first.output.id)) == 1


def test_run_transitions_status_and_appends_event(db_session: Session) -> None:
    """design.md §3: a status change appends an event, never overwrites history."""
    ctx = _make_context(db_session)
    posting = _posting(db_session)
    agent = ApplicationTrackingAgent()
    agent.run(ApplicationTrackingInput(job_posting=posting), ctx)

    result = agent.run(
        ApplicationTrackingInput(
            job_posting=posting, status=ApplicationStatus.SUBMITTED, note="Sent via email"
        ),
        ctx,
    )

    assert result.output.status == ApplicationStatus.SUBMITTED
    events = ctx.repos.applications.list_events(result.output.id)
    assert [e.to_status for e in events] == [ApplicationStatus.DRAFTED, ApplicationStatus.SUBMITTED]
    assert events[-1].note == "Sent via email"


def test_run_status_update_can_create_directly(db_session: Session) -> None:
    """A status-update call with no prior application creates one at that status."""
    ctx = _make_context(db_session)
    posting = _posting(db_session)
    agent = ApplicationTrackingAgent()

    result = agent.run(
        ApplicationTrackingInput(job_posting=posting, status=ApplicationStatus.SUBMITTED), ctx
    )

    assert result.output.status == ApplicationStatus.SUBMITTED


def test_run_warns_when_documents_given_for_existing_application(db_session: Session) -> None:
    """Resume/cover-letter references are creation-time only; a later attempt warns."""
    ctx = _make_context(db_session)
    posting = _posting(db_session)
    resume_version = _resume_version(db_session, posting.id)
    agent = ApplicationTrackingAgent()
    agent.run(ApplicationTrackingInput(job_posting=posting), ctx)

    result = agent.run(
        ApplicationTrackingInput(job_posting=posting, resume_version=resume_version), ctx
    )

    assert result.output.resume_version_id is None  # not retroactively updated
    assert any("not updated" in warning for warning in result.warnings)


def test_run_raises_on_unpersisted_posting(db_session: Session) -> None:
    ctx = _make_context(db_session)
    agent = ApplicationTrackingAgent()
    posting = JobPosting(source="greenhouse", source_id="1", title="X", url="https://x/1")

    with pytest.raises(ValueError, match="already-persisted"):
        agent.run(ApplicationTrackingInput(job_posting=posting), ctx)


def test_run_raises_when_resume_version_belongs_to_different_posting(db_session: Session) -> None:
    ctx = _make_context(db_session)
    posting_a = _posting(db_session, source_id="1")
    posting_b = _posting(db_session, source_id="2")
    resume_version = _resume_version(db_session, posting_b.id)
    agent = ApplicationTrackingAgent()

    with pytest.raises(ValueError, match="job_posting_id"):
        agent.run(
            ApplicationTrackingInput(job_posting=posting_a, resume_version=resume_version), ctx
        )


def test_export_applications_csv_matches_hand_computed_status_counts() -> None:
    """phases.md Phase 14 AC: CSV export matches hand-computed fixture aggregates."""
    applications = [
        Application(id="1", job_posting_id="p1", status=ApplicationStatus.SUBMITTED),
        Application(id="2", job_posting_id="p2", status=ApplicationStatus.SUBMITTED),
        Application(id="3", job_posting_id="p3", status=ApplicationStatus.OFFER),
    ]
    expected_counts = {"submitted": 2, "offer": 1}

    csv_text = export_applications_csv(applications)

    import csv as csv_module
    import io

    rows = list(csv_module.DictReader(io.StringIO(csv_text)))
    actual_counts: dict[str, int] = {}
    for row in rows:
        actual_counts[row["status"]] = actual_counts.get(row["status"], 0) + 1

    assert actual_counts == expected_counts
    assert rows[0]["job_posting_id"] == "p1"


def test_export_applications_csv_empty_list_produces_header_only() -> None:
    csv_text = export_applications_csv([])

    lines = csv_text.strip().splitlines()
    assert len(lines) == 1
    assert "status" in lines[0]
