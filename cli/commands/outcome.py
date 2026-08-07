"""`jobhunt outcome` -- record a status transition for a tracked application.

tasks.md T14.3.
"""

from __future__ import annotations

from typing import ClassVar

from sqlalchemy.orm import Session

from cli.commands.setup import ensure_migrated
from jobhunt_core.agents.application_tracking_agent import (
    ApplicationTrackingAgent,
    ApplicationTrackingInput,
)
from jobhunt_core.agents.base import RunContext
from jobhunt_core.config.settings import Settings, load_settings
from jobhunt_core.errors import JobHuntError
from jobhunt_core.llm.provider import LLMProvider
from jobhunt_core.logging_config import configure_logging
from jobhunt_core.orchestration.context import build_repository_bundle, build_sources
from jobhunt_core.schemas.application import Application, ApplicationStatus
from jobhunt_core.storage.db import create_session_factory, create_sqlite_engine


class _UnusedLLMProvider:
    """Placeholder ``LLMProvider`` for a purely deterministic agent (agents.md §9).

    ``build_run_context()`` always constructs a real ``LLMProvider``
    (requiring the default provider's API key), which every other CLI
    command needs but this one never does -- Application Tracking
    Agent makes no LLM call at all. Requiring an API key just to record
    a status change would be a real, avoidable footgun for a command a
    user might run standalone, so this command builds its own
    lightweight ``RunContext`` instead of using ``build_run_context()``.
    """

    name: ClassVar[str] = "unused"

    def complete(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("ApplicationTrackingAgent should never call the LLM")

    def complete_structured(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("ApplicationTrackingAgent should never call the LLM")


def _build_tracking_context(settings: Settings, session: Session) -> RunContext:
    """Build a ``RunContext`` with no real ``LLMProvider`` -- see ``_UnusedLLMProvider``."""
    llm: LLMProvider = _UnusedLLMProvider()  # type: ignore[assignment]
    return RunContext(
        settings=settings,
        llm=llm,
        repos=build_repository_bundle(session),
        sources=build_sources(settings),
    )


def run_outcome_with_context(
    job_posting_id: str, status: ApplicationStatus, note: str | None, ctx: RunContext
) -> Application:
    """Record a status transition for the application tied to ``job_posting_id``.

    Split out from :func:`run_outcome` so tests can inject a
    ``RunContext`` directly, same pattern as ``cli/commands/rank.py``.

    Raises:
        JobHuntError: No job posting, or no application yet, exists
            for ``job_posting_id``.
    """
    posting = ctx.repos.jobs.get(job_posting_id)
    if posting is None:
        raise JobHuntError(
            f"No job posting found with id {job_posting_id}.",
            remedy="Check the job_posting_id and try again.",
        )
    existing = ctx.repos.applications.get_by_job_posting(job_posting_id)
    if existing is None:
        raise JobHuntError(
            f"No application exists yet for job posting {job_posting_id}.",
            remedy="Create the application first (e.g. via the Application Tracking "
            "Agent's create mode) before recording an outcome.",
        )

    agent = ApplicationTrackingAgent()
    result = agent.run(ApplicationTrackingInput(job_posting=posting, status=status, note=note), ctx)
    return result.output


def run_outcome(
    job_posting_id: str,
    status: ApplicationStatus,
    *,
    note: str | None = None,
    settings: Settings | None = None,
) -> Application:
    """Load settings, migrate, and record a status transition.

    Args:
        job_posting_id: The job posting whose application changed.
        status: The new status.
        note: Optional freeform note about the change.
        settings: Injected settings (tests); loads real settings from
            ``config/`` and the environment if omitted.

    Returns:
        The updated ``Application``.
    """
    resolved_settings = settings or load_settings()
    configure_logging(resolved_settings.data_dir / "logs")
    ensure_migrated(resolved_settings.data_dir)

    engine = create_sqlite_engine(resolved_settings.data_dir / "jobhunt.db")
    session_factory = create_session_factory(engine)
    session: Session = session_factory()
    try:
        ctx = _build_tracking_context(resolved_settings, session)
        application = run_outcome_with_context(job_posting_id, status, note, ctx)
        session.commit()
        return application
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def outcome_command(job_posting_id: str, status: ApplicationStatus, note: str = "") -> None:
    """Record a status change for a tracked application.

    Args:
        job_posting_id: The job posting whose application changed.
        status: The new status (drafted/submitted/screening/
            interview_scheduled/interview_completed/offer/rejected/
            withdrawn).
        note: Optional freeform note about the change.
    """
    application = run_outcome(job_posting_id, status, note=note or None)
    print(f"Application {application.id} -> {application.status.value}")
    if note:
        print(f"  Note: {note}")
