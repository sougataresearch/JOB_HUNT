"""Tests for the Career Analytics Agent (tasks.md T16.1, phases.md Phase 16).

No LLM call at all (agents.md §11: "writes nothing (pure
computation)") -- every test uses a real repo-backed ``RunContext``
with a placeholder LLM that must never be called. Rates are checked
against hand-computed fixture aggregates (agents.md §11 Metrics).
"""

from typing import ClassVar

from sqlalchemy.orm import Session

from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.agents.career_analytics_agent import CareerAnalyticsAgent, CareerAnalyticsInput
from jobhunt_core.config.settings import LLMConfig, Settings
from jobhunt_core.schemas.application import Application, ApplicationStatus
from jobhunt_core.schemas.job import JobPosting
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
        raise AssertionError("CareerAnalyticsAgent should never call the LLM")

    def complete_structured(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("CareerAnalyticsAgent should never call the LLM")


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


def test_run_reports_insufficient_data_below_five_submitted(db_session: Session) -> None:
    """agents.md §11 Failure handling: <5 submitted applications withholds rates."""
    ctx = _make_context(db_session)
    jobs = JobRepo(db_session)
    applications = ApplicationRepo(db_session)
    # create() is idempotent per job_posting_id, so each of the 4 rows
    # needs its own posting to actually count as 4 distinct applications.
    for i in range(4):
        posting = jobs.save(
            JobPosting(
                source="greenhouse", source_id=str(i), title="Engineer", url=f"https://x/{i}"
            )
        )
        applications.create(
            Application(job_posting_id=posting.id, status=ApplicationStatus.SUBMITTED)
        )

    agent = CareerAnalyticsAgent()
    result = agent.run(CareerAnalyticsInput(), ctx)

    assert result.output.insufficient_data is True
    assert result.output.overall_response_rate is None
    assert any("not enough data" in warning for warning in result.warnings)


def _seed_hand_computed_fixture(db_session: Session) -> None:
    """Seed the exact fixture this test file's docstring math is computed against.

    Postings (one per application -- ``applications`` is one-row-per-
    posting, database.md §9): four titled "Backend Engineer" (two
    "greenhouse", two "manual_import"), two titled "Frontend Engineer"
    (both "greenhouse"). Applications: app1 SUBMITTED, app2 SCREENING
    (both backend/greenhouse), app3 INTERVIEW_SCHEDULED, app4 OFFER
    (both backend/manual_import), app5 REJECTED, app6 WITHDRAWN (both
    frontend/greenhouse).

    Hand-computed expected rates:
    - Overall (6 submitted): response 4/6, interview 2/6, offer 1/6
      (responded = app2,3,4,5; interviewed = app3,4; offered = app4).
    - By role "Backend Engineer" (app1-4): response 3/4, interview 2/4,
      offer 1/4.
    - By role "Frontend Engineer" (app5-6): response 1/2, interview 0,
      offer 0.
    - By source "greenhouse" (app1,2,5,6): response 2/4, interview 0,
      offer 0.
    - By source "manual_import" (app3,4): response 2/2, interview 2/2,
      offer 1/2.
    """
    jobs = JobRepo(db_session)
    applications = ApplicationRepo(db_session)

    def _posting(source_id: str, *, title: str, source: str) -> str:
        posting = jobs.save(
            JobPosting(
                source=source, source_id=source_id, title=title, url=f"https://x/{source_id}"
            )
        )
        return posting.id

    app1_posting = _posting("1", title="Backend Engineer", source="greenhouse")
    app2_posting = _posting("2", title="Backend Engineer", source="greenhouse")
    app3_posting = _posting("3", title="Backend Engineer", source="manual_import")
    app4_posting = _posting("4", title="Backend Engineer", source="manual_import")
    app5_posting = _posting("5", title="Frontend Engineer", source="greenhouse")
    app6_posting = _posting("6", title="Frontend Engineer", source="greenhouse")

    applications.create(
        Application(job_posting_id=app1_posting, status=ApplicationStatus.SUBMITTED)
    )

    app2 = applications.create(Application(job_posting_id=app2_posting))
    applications.change_status(app2.id, ApplicationStatus.SCREENING)

    app3 = applications.create(Application(job_posting_id=app3_posting))
    applications.change_status(app3.id, ApplicationStatus.INTERVIEW_SCHEDULED)

    app4 = applications.create(Application(job_posting_id=app4_posting))
    applications.change_status(app4.id, ApplicationStatus.OFFER)

    app5 = applications.create(Application(job_posting_id=app5_posting))
    applications.change_status(app5.id, ApplicationStatus.REJECTED)

    app6 = applications.create(Application(job_posting_id=app6_posting))
    applications.change_status(app6.id, ApplicationStatus.WITHDRAWN)


def test_run_computes_hand_verified_overall_and_breakdown_rates(db_session: Session) -> None:
    """agents.md §11 Metrics: numeric correctness against hand-computed fixture aggregates."""
    _seed_hand_computed_fixture(db_session)
    ctx = _make_context(db_session)
    agent = CareerAnalyticsAgent()

    result = agent.run(CareerAnalyticsInput(), ctx)
    report = result.output

    assert report.insufficient_data is False
    assert report.total_submitted == 6
    assert report.overall_response_rate == 4 / 6
    assert report.overall_interview_rate == 2 / 6
    assert report.overall_offer_rate == 1 / 6

    by_role = {row.key: row for row in report.by_role_type}
    assert by_role["Backend Engineer"].total_submitted == 4
    assert by_role["Backend Engineer"].response_rate == 3 / 4
    assert by_role["Backend Engineer"].interview_rate == 2 / 4
    assert by_role["Backend Engineer"].offer_rate == 1 / 4
    assert by_role["Frontend Engineer"].total_submitted == 2
    assert by_role["Frontend Engineer"].response_rate == 1 / 2
    assert by_role["Frontend Engineer"].interview_rate == 0.0

    by_source = {row.key: row for row in report.by_source}
    assert by_source["greenhouse"].total_submitted == 4
    assert by_source["greenhouse"].response_rate == 2 / 4
    assert by_source["manual_import"].total_submitted == 2
    assert by_source["manual_import"].response_rate == 1.0
    assert by_source["manual_import"].interview_rate == 1.0
    assert by_source["manual_import"].offer_rate == 0.5


def test_run_excludes_drafted_applications_from_totals(db_session: Session) -> None:
    """A drafted (not-yet-submitted) application never counts toward rates."""
    _seed_hand_computed_fixture(db_session)
    jobs = JobRepo(db_session)
    posting = jobs.save(
        JobPosting(
            source="greenhouse", source_id="draft", title="Draft Role", url="https://x/draft"
        )
    )
    ApplicationRepo(db_session).create(Application(job_posting_id=posting.id))
    ctx = _make_context(db_session)
    agent = CareerAnalyticsAgent()

    result = agent.run(CareerAnalyticsInput(), ctx)

    assert result.output.total_applications == 7
    assert result.output.total_submitted == 6
    assert "Draft Role" not in {row.key for row in result.output.by_role_type}
