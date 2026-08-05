"""`jobhunt setup` -- onboarding: CV file -> persisted CandidateProfile.

tasks.md T5.3.
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy.orm import Session

from jobhunt_core.agents.base import RunContext
from jobhunt_core.agents.resume_analysis_agent import ResumeAnalysisAgent, ResumeAnalysisInput
from jobhunt_core.config.settings import Settings, load_settings
from jobhunt_core.logging_config import configure_logging
from jobhunt_core.orchestration.context import build_run_context
from jobhunt_core.schemas.profile import CandidateProfile
from jobhunt_core.storage.db import create_session_factory, create_sqlite_engine

REPO_ROOT = Path(__file__).resolve().parents[2]


def ensure_migrated(data_dir: Path) -> None:
    """Run ``alembic upgrade head`` against ``data_dir``'s ``jobhunt.db``.

    Args:
        data_dir: The data directory the DB lives (or will be created) in.
    """
    os.environ["JOBHUNT_DATA_DIR"] = str(data_dir)
    config = AlembicConfig(str(REPO_ROOT / "alembic.ini"))
    alembic_command.upgrade(config, "head")


def run_setup_with_context(cv_file_path: Path, ctx: RunContext) -> CandidateProfile:
    """Run the Resume Analysis Agent on ``cv_file_path`` and persist the result.

    Split out from :func:`run_setup` so tests can inject a
    ``RunContext`` built with a fake ``LLMProvider``, never making a
    live LLM call (testing.md, rules.md §Testing Requirements).

    Args:
        cv_file_path: Path to the candidate's CV.
        ctx: An already-constructed run context.

    Returns:
        The persisted ``CandidateProfile``.
    """
    agent = ResumeAnalysisAgent()
    result = agent.run(ResumeAnalysisInput(cv_file_path=cv_file_path), ctx)
    return ctx.repos.profiles.save(result.output)


def run_setup(cv_file_path: Path, *, settings: Settings | None = None) -> CandidateProfile:
    """Run the full onboarding flow: load settings, migrate, extract, persist.

    Args:
        cv_file_path: Path to the candidate's CV (PDF, DOCX, or Markdown).
        settings: Injected settings (tests); loads real settings from
            ``config/`` and the environment if omitted.

    Returns:
        The persisted ``CandidateProfile``.
    """
    resolved_settings = settings or load_settings()
    configure_logging(resolved_settings.data_dir / "logs")
    ensure_migrated(resolved_settings.data_dir)

    engine = create_sqlite_engine(resolved_settings.data_dir / "jobhunt.db")
    session_factory = create_session_factory(engine)
    session: Session = session_factory()
    try:
        ctx = build_run_context(resolved_settings, session, agent_name="resume_analysis")
        profile = run_setup_with_context(cv_file_path, ctx)
        session.commit()
        return profile
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def setup_command(
    cv_file: Path,
) -> None:
    """Parse a CV and create your candidate profile.

    Args:
        cv_file: Path to your CV (PDF, DOCX, or Markdown).
    """
    profile = run_setup(cv_file)
    name = profile.full_name or "(name not found)"
    print(f"Saved CandidateProfile {profile.id} for {name}")
    print(f"  Skills extracted: {len(profile.skills)}")
    print(f"  Experience entries: {len(profile.experience)}")
    if not profile.email:
        print("  Note: email not found in CV -- add it manually if needed.")
