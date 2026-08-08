"""`jobhunt report` -- generate the static HTML career analytics dashboard.

tasks.md T16.2, design.md §1.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from sqlalchemy.orm import Session

from cli.commands.setup import ensure_migrated
from jobhunt_core.agents.base import RunContext
from jobhunt_core.agents.career_analytics_agent import CareerAnalyticsAgent, CareerAnalyticsInput
from jobhunt_core.config.settings import Settings, load_settings
from jobhunt_core.documents.report_renderer import write_report_html
from jobhunt_core.llm.provider import LLMProvider
from jobhunt_core.logging_config import configure_logging
from jobhunt_core.orchestration.context import build_repository_bundle, build_sources
from jobhunt_core.schemas.analytics import AnalyticsReport
from jobhunt_core.storage.db import create_session_factory, create_sqlite_engine


class _UnusedLLMProvider:
    """Placeholder ``LLMProvider`` -- Career Analytics's core stats never call one (agents.md §11).

    Same reasoning as ``cli/commands/outcome.py``'s own
    ``_UnusedLLMProvider``: ``build_run_context()`` always constructs a
    real, API-key-requiring provider, which this deterministic agent
    never needs.
    """

    name: ClassVar[str] = "unused"

    def complete(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("CareerAnalyticsAgent should never call the LLM")

    def complete_structured(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("CareerAnalyticsAgent should never call the LLM")


def _build_analytics_context(settings: Settings, session: Session) -> RunContext:
    """Build a ``RunContext`` with no real ``LLMProvider`` -- see ``_UnusedLLMProvider``."""
    llm: LLMProvider = _UnusedLLMProvider()  # type: ignore[assignment]
    return RunContext(
        settings=settings,
        llm=llm,
        repos=build_repository_bundle(session),
        sources=build_sources(settings),
    )


def run_report_with_context(ctx: RunContext) -> AnalyticsReport:
    """Run the Career Analytics Agent and return its report.

    Split out from :func:`run_report` so tests can inject a
    ``RunContext`` directly, same pattern as ``cli/commands/rank.py``.
    """
    agent = CareerAnalyticsAgent()
    result = agent.run(CareerAnalyticsInput(), ctx)
    return result.output


def run_report(*, output_path: Path | None = None, settings: Settings | None = None) -> Path:
    """Load settings, migrate, compute the report, and write it as HTML.

    Args:
        output_path: Where to write the HTML file; defaults to
            ``<data_dir>/report.html``.
        settings: Injected settings (tests); loads real settings from
            ``config/`` and the environment if omitted.

    Returns:
        The path the report was written to.
    """
    resolved_settings = settings or load_settings()
    configure_logging(resolved_settings.data_dir / "logs")
    ensure_migrated(resolved_settings.data_dir)

    engine = create_sqlite_engine(resolved_settings.data_dir / "jobhunt.db")
    session_factory = create_session_factory(engine)
    session: Session = session_factory()
    try:
        ctx = _build_analytics_context(resolved_settings, session)
        report = run_report_with_context(ctx)
        resolved_output = output_path or (resolved_settings.data_dir / "report.html")
        return write_report_html(report, resolved_output)
    finally:
        session.close()


def report_command(output: str = "") -> None:
    """Generate the static HTML career analytics dashboard.

    Args:
        output: Optional output file path; defaults to
            ``<data_dir>/report.html``.
    """
    output_path = Path(output) if output else None
    path = run_report(output_path=output_path)
    print(f"Wrote report to {path}")
