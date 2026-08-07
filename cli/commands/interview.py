"""`jobhunt interview` -- prepare interview questions for a scheduled interview.

tasks.md T15.1, phases.md Phase 15 Deliverables ("/interview command
trigger on status change").
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from cli.commands.setup import ensure_migrated
from jobhunt_core.agents.base import RunContext
from jobhunt_core.agents.interview_prep_agent import InterviewPrepAgent, InterviewPrepInput
from jobhunt_core.config.settings import Settings, load_settings
from jobhunt_core.errors import JobHuntError
from jobhunt_core.logging_config import configure_logging
from jobhunt_core.orchestration.context import build_run_context
from jobhunt_core.schemas.application import ApplicationStatus
from jobhunt_core.schemas.interview import InterviewPrepPack, InterviewType
from jobhunt_core.storage.db import create_session_factory, create_sqlite_engine


def run_interview_with_context(
    job_posting_id: str, interview_type: InterviewType, ctx: RunContext
) -> InterviewPrepPack:
    """Resolve the application/resume/match-score for a posting and run Interview Prep.

    Split out from :func:`run_interview` so tests can inject a
    ``RunContext`` directly, same pattern as ``cli/commands/rank.py``.

    Raises:
        JobHuntError: No posting, application, resume version, or match
            score exists yet, or the application's status isn't
            ``interview_scheduled`` (agents.md §10's own trigger
            condition -- enforced here explicitly since no
            event-driven orchestrator exists yet to enforce it
            automatically, per ``AgentResult``'s own docstring).
    """
    posting = ctx.repos.jobs.get(job_posting_id)
    if posting is None:
        raise JobHuntError(
            f"No job posting found with id {job_posting_id}.",
            remedy="Check the job_posting_id and try again.",
        )
    application = ctx.repos.applications.get_by_job_posting(job_posting_id)
    if application is None:
        raise JobHuntError(
            f"No application exists yet for job posting {job_posting_id}.",
            remedy="Create the application first, then record status "
            "'interview_scheduled' via `jobhunt outcome`.",
        )
    if application.status != ApplicationStatus.INTERVIEW_SCHEDULED:
        raise JobHuntError(
            f"Application {application.id} has status '{application.status.value}', "
            "not 'interview_scheduled'.",
            remedy="Record the status transition first: "
            "`jobhunt outcome <job_posting_id> interview_scheduled`.",
        )
    if application.resume_version_id is None:
        raise JobHuntError(
            f"Application {application.id} has no linked resume version.",
            remedy="Generate a tailored resume for this posting first.",
        )
    resume_version = ctx.repos.documents.get_resume_version(application.resume_version_id)
    if resume_version is None:
        raise JobHuntError(f"ResumeVersion {application.resume_version_id} not found.")

    scores = ctx.repos.matches.list(
        job_posting_id=job_posting_id, profile_id=resume_version.profile_id
    )
    if not scores:
        raise JobHuntError(
            f"No MatchScore found for job posting {job_posting_id}.",
            remedy="Run Job Matching for this posting first.",
        )
    match_score = max(scores, key=lambda score: score.created_at or datetime.min)

    agent = InterviewPrepAgent()
    result = agent.run(
        InterviewPrepInput(
            application=application,
            job_posting=posting,
            resume_version=resume_version,
            match_score=match_score,
            interview_type=interview_type,
        ),
        ctx,
    )
    return result.output


def run_interview(
    job_posting_id: str, interview_type: InterviewType, *, settings: Settings | None = None
) -> InterviewPrepPack:
    """Load settings, migrate, and prepare interview questions.

    Args:
        job_posting_id: The job posting whose application is being
            interviewed for.
        interview_type: The kind of interview being prepared for.
        settings: Injected settings (tests); loads real settings from
            ``config/`` and the environment if omitted.

    Returns:
        The generated ``InterviewPrepPack``.
    """
    resolved_settings = settings or load_settings()
    configure_logging(resolved_settings.data_dir / "logs")
    ensure_migrated(resolved_settings.data_dir)

    engine = create_sqlite_engine(resolved_settings.data_dir / "jobhunt.db")
    session_factory = create_session_factory(engine)
    session: Session = session_factory()
    try:
        ctx = build_run_context(resolved_settings, session, agent_name="interview_prep")
        pack = run_interview_with_context(job_posting_id, interview_type, ctx)
        session.commit()
        return pack
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def interview_command(job_posting_id: str, interview_type: InterviewType) -> None:
    """Generate interview prep questions for a scheduled interview.

    Args:
        job_posting_id: The job posting whose application is being
            interviewed for.
        interview_type: phone_screen/technical/onsite/final.
    """
    pack = run_interview(job_posting_id, interview_type)
    print(
        f"Interview {pack.interview.id} ({interview_type.value}) -- {len(pack.questions)} questions"
    )
    for question in pack.questions:
        print(f"\n[{question.category.value}] {question.question}")
        for point in question.suggested_talking_points:
            print(f"  - {point}")
