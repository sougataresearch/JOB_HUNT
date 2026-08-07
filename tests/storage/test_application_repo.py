"""Round-trip tests for ApplicationRepo (phases.md Phase 4/14 acceptance criteria)."""

from sqlalchemy.orm import Session

from jobhunt_core.schemas.application import Application, ApplicationStatus
from jobhunt_core.schemas.document import CoverLetter, ResumeVersion
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.profile import CandidateProfile
from jobhunt_core.storage.repositories.application_repo import ApplicationRepo
from jobhunt_core.storage.repositories.document_repo import DocumentRepo
from jobhunt_core.storage.repositories.job_repo import JobRepo
from jobhunt_core.storage.repositories.profile_repo import ProfileRepo


def _seed_job(db_session: Session) -> str:
    job = JobRepo(db_session).save(
        JobPosting(source="greenhouse", source_id="1", title="Engineer", url="https://x/1")
    )
    return job.id


def test_round_trip_write_then_read(db_session: Session) -> None:
    """A created application reads back with every field intact."""
    job_id = _seed_job(db_session)
    repo = ApplicationRepo(db_session)

    saved = repo.create(Application(job_posting_id=job_id))
    fetched = repo.get(saved.id)

    assert fetched is not None
    assert fetched.job_posting_id == job_id
    assert fetched.status == ApplicationStatus.DRAFTED


def test_create_records_initial_event(db_session: Session) -> None:
    """Creating an application appends a from_status=None -> DRAFTED event."""
    job_id = _seed_job(db_session)
    repo = ApplicationRepo(db_session)

    application = repo.create(Application(job_posting_id=job_id))
    events = repo.list_events(application.id)

    assert len(events) == 1
    assert events[0].from_status is None
    assert events[0].to_status == ApplicationStatus.DRAFTED


def test_create_is_idempotent_per_job_posting(db_session: Session) -> None:
    """Creating twice for the same job_posting_id returns the existing record."""
    job_id = _seed_job(db_session)
    repo = ApplicationRepo(db_session)

    first = repo.create(Application(job_posting_id=job_id))
    second = repo.create(Application(job_posting_id=job_id))

    assert first.id == second.id
    assert len(repo.list_events(first.id)) == 1  # not duplicated


def test_round_trip_persists_document_references(db_session: Session) -> None:
    """resume_version_id/cover_letter_id (Phase 14) round-trip like every other column."""
    job_id = _seed_job(db_session)
    profile_id = ProfileRepo(db_session).save(CandidateProfile(full_name="Jane Doe")).id
    documents = DocumentRepo(db_session)
    resume_template = documents.get_or_create_template(
        kind="resume", name="resume", file_path="cv/resume.tex.jinja"
    )
    resume_version = documents.save_resume_version(
        ResumeVersion(
            profile_id=profile_id,
            job_posting_id=job_id,
            template_id=resume_template.id or "",
            rendered_pdf_path="r.pdf",
            rendered_tex_path="r.tex",
            ats_verification_passed=True,
            ats_extracted_text_path="r.txt",
        )
    )
    cover_letter_template = documents.get_or_create_template(
        kind="cover_letter", name="cover_letter", file_path="cover_letter/cover_letter.tex.jinja"
    )
    cover_letter = documents.save_cover_letter(
        CoverLetter(
            job_posting_id=job_id,
            resume_version_id=resume_version.id,
            template_id=cover_letter_template.id or "",
            rendered_pdf_path="cl.pdf",
            rendered_tex_path="cl.tex",
        )
    )
    repo = ApplicationRepo(db_session)

    saved = repo.create(
        Application(
            job_posting_id=job_id,
            resume_version_id=resume_version.id,
            cover_letter_id=cover_letter.id,
        )
    )
    fetched = repo.get(saved.id)

    assert fetched is not None
    assert fetched.resume_version_id == resume_version.id
    assert fetched.cover_letter_id == cover_letter.id


def test_change_status_updates_current_state_and_appends_event(db_session: Session) -> None:
    """change_status() updates status and appends a from->to event (design.md §3)."""
    job_id = _seed_job(db_session)
    repo = ApplicationRepo(db_session)
    application = repo.create(Application(job_posting_id=job_id))

    updated = repo.change_status(
        application.id, ApplicationStatus.SUBMITTED, note="Submitted via email"
    )

    assert updated.status == ApplicationStatus.SUBMITTED
    events = repo.list_events(application.id)
    assert len(events) == 2
    assert events[1].from_status == ApplicationStatus.DRAFTED
    assert events[1].to_status == ApplicationStatus.SUBMITTED
    assert events[1].note == "Submitted via email"


def test_status_history_is_never_overwritten(db_session: Session) -> None:
    """Multiple transitions accumulate events rather than replacing them."""
    job_id = _seed_job(db_session)
    repo = ApplicationRepo(db_session)
    application = repo.create(Application(job_posting_id=job_id))

    repo.change_status(application.id, ApplicationStatus.SUBMITTED)
    repo.change_status(application.id, ApplicationStatus.SCREENING)
    repo.change_status(application.id, ApplicationStatus.INTERVIEW_SCHEDULED)

    events = repo.list_events(application.id)
    assert [e.to_status for e in events] == [
        ApplicationStatus.DRAFTED,
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.SCREENING,
        ApplicationStatus.INTERVIEW_SCHEDULED,
    ]
