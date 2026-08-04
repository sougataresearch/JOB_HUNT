"""Round-trip tests for InterviewRepo (phases.md Phase 4 acceptance criteria)."""

from sqlalchemy.orm import Session

from jobhunt_core.schemas.application import Application
from jobhunt_core.schemas.interview import (
    Interview,
    InterviewQuestion,
    InterviewType,
    QuestionCategory,
)
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.storage.repositories.application_repo import ApplicationRepo
from jobhunt_core.storage.repositories.interview_repo import InterviewRepo
from jobhunt_core.storage.repositories.job_repo import JobRepo


def _seed_application(db_session: Session) -> str:
    job = JobRepo(db_session).save(
        JobPosting(source="greenhouse", source_id="1", title="Engineer", url="https://x/1")
    )
    application = ApplicationRepo(db_session).create(Application(job_posting_id=job.id))
    return application.id


def test_round_trip_write_then_read(db_session: Session) -> None:
    """A saved interview reads back with every field intact, including the enum."""
    application_id = _seed_application(db_session)
    repo = InterviewRepo(db_session)

    saved = repo.save(
        Interview(application_id=application_id, interview_type=InterviewType.TECHNICAL)
    )
    fetched = repo.get(saved.id)

    assert fetched is not None
    assert fetched.interview_type == InterviewType.TECHNICAL
    assert fetched.application_id == application_id


def test_add_and_list_questions(db_session: Session) -> None:
    """Prepared questions round-trip, including their talking points."""
    application_id = _seed_application(db_session)
    repo = InterviewRepo(db_session)
    interview = repo.save(
        Interview(application_id=application_id, interview_type=InterviewType.PHONE_SCREEN)
    )

    repo.add_question(
        InterviewQuestion(
            interview_id=interview.id,
            category=QuestionCategory.BEHAVIORAL,
            question="Tell me about a conflict you resolved.",
            suggested_talking_points=["Resume bullet: led cross-team migration"],
        )
    )
    repo.add_question(
        InterviewQuestion(
            interview_id=interview.id,
            category=QuestionCategory.TECHNICAL,
            question="How would you design a rate limiter?",
        )
    )

    questions = repo.list_questions(interview.id)

    assert len(questions) == 2
    categories = {q.category for q in questions}
    assert categories == {QuestionCategory.BEHAVIORAL, QuestionCategory.TECHNICAL}
