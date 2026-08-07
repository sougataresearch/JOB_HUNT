"""`jobhunt rank` -- ranked, paginated shortlist of scored postings.

tasks.md T9.1.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from cli.commands.setup import ensure_migrated
from jobhunt_core.config.settings import Settings, load_settings
from jobhunt_core.errors import JobHuntError
from jobhunt_core.logging_config import configure_logging
from jobhunt_core.orchestration.ranking import latest_per_posting, paginate, rank
from jobhunt_core.schemas.match import RankedPosting
from jobhunt_core.storage.db import create_session_factory, create_sqlite_engine
from jobhunt_core.storage.repositories import MatchRepo, ProfileRepo


def run_rank_with_session(
    session: Session, *, page: int = 1, page_size: int = 10
) -> list[RankedPosting]:
    """Rank and paginate the active profile's latest scores.

    Split out from :func:`run_rank` so tests can inject a session
    directly, same pattern as ``cli/commands/setup.py``'s
    ``run_setup_with_context`` -- no LLM call anywhere in this command
    at all (``ranking.py`` is a pure function, api.md §3), so there
    isn't even a fake to inject, just real repos against a scratch DB.

    Args:
        session: An open SQLAlchemy session.
        page: 1-indexed page number (design.md §2 progressive disclosure).
        page_size: Entries per page.

    Returns:
        The requested page of ``RankedPosting`` entries.

    Raises:
        JobHuntError: No active candidate profile exists yet.
    """
    profile = ProfileRepo(session).get_active()
    if profile is None or profile.id is None:
        raise JobHuntError(
            "No active candidate profile found.", remedy="Run `jobhunt setup <cv_file>` first."
        )
    scores = MatchRepo(session).list(profile_id=profile.id)
    ranked = rank(latest_per_posting(scores))
    return paginate(ranked, page=page, page_size=page_size)


def run_rank(
    *, page: int = 1, page_size: int = 10, settings: Settings | None = None
) -> list[RankedPosting]:
    """Load settings, migrate, and return one ranked page for the active profile.

    Args:
        page: 1-indexed page number.
        page_size: Entries per page.
        settings: Injected settings (tests); loads real settings from
            ``config/`` and the environment if omitted.

    Returns:
        The requested page of ``RankedPosting`` entries.
    """
    resolved_settings = settings or load_settings()
    configure_logging(resolved_settings.data_dir / "logs")
    ensure_migrated(resolved_settings.data_dir)

    engine = create_sqlite_engine(resolved_settings.data_dir / "jobhunt.db")
    session_factory = create_session_factory(engine)
    session: Session = session_factory()
    try:
        return run_rank_with_session(session, page=page, page_size=page_size)
    finally:
        session.close()


def rank_command(page: int = 1, page_size: int = 10) -> None:
    """Show a ranked, paginated shortlist of scored postings.

    Args:
        page: 1-indexed page number.
        page_size: Entries per page (design.md §2: default ~10).
    """
    ranked_page = run_rank(page=page, page_size=page_size)
    if not ranked_page:
        print(f"No ranked postings on page {page}.")
        return
    for entry in ranked_page:
        print(f"#{entry.rank}  score={entry.score.score:.0f}  job_posting_id={entry.job_id}")
        print(f"      {entry.score.rationale}")
