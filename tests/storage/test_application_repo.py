"""Round-trip tests for ApplicationRepo (phases.md Phase 4 acceptance criteria)."""

from sqlalchemy.orm import Session

from jobhunt_core.schemas.application import Application, ApplicationStatus
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.storage.repositories.application_repo import ApplicationRepo
from jobhunt_core.storage.repositories.job_repo import JobRepo


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
