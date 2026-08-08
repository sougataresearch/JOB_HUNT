"""Career Analytics Agent — aggregates application history into AnalyticsReport.

agents.md §11. Eleventh agent in the core pipeline (architecture.md
§3.1). Purely deterministic (no LLM call for the core statistics --
rules.md §Performance Guidelines: "no agent should require an LLM
call for something a deterministic function can compute"). agents.md
§11 also mentions an *optional* LLM-generated narrative summary layer
("purely for prose, never for the numbers") -- deferred here:
tasks.md T16.1's own Expected files list has no prompt file, and
phases.md Phase 16's acceptance criteria only requires numeric
correctness on fixture data, not narrative prose. A disclosed scope
choice (rules.md AI Coding Rule 2), not a silently dropped one.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from typing import ClassVar

from pydantic import BaseModel

from jobhunt_core.agents.base import AgentResult, RunContext
from jobhunt_core.orchestration.registry import register_agent
from jobhunt_core.schemas.analytics import AnalyticsReport, RateBreakdown
from jobhunt_core.schemas.application import Application, ApplicationStatus
from jobhunt_core.schemas.job import JobPosting

_MIN_APPLICATIONS_FOR_RATES = 5
# agents.md §11 Failure handling's own example: "insufficient history
# (e.g., <5 applications)" -- doc-specified, not this implementation's
# own threshold choice.

_RESPONDED_STATUSES = {
    ApplicationStatus.SCREENING,
    ApplicationStatus.INTERVIEW_SCHEDULED,
    ApplicationStatus.INTERVIEW_COMPLETED,
    ApplicationStatus.OFFER,
    ApplicationStatus.REJECTED,
}
_INTERVIEWED_STATUSES = {
    ApplicationStatus.INTERVIEW_SCHEDULED,
    ApplicationStatus.INTERVIEW_COMPLETED,
    ApplicationStatus.OFFER,
}


class CareerAnalyticsInput(BaseModel):
    """Input to the Career Analytics Agent (agents.md §11).

    No per-run parameters -- the agent reads every application for
    the user directly from the repositories (agents.md §11 Memory).
    """


@register_agent("career_analytics")
class CareerAnalyticsAgent:
    """Computes response/interview/offer rates overall, by role title, and by source.

    Writes nothing (agents.md §11 Memory: "writes nothing (pure
    computation)"). Never reports a rate from a sample too small to
    mean anything (agents.md §11 Failure handling) -- see
    ``AnalyticsReport.insufficient_data``.
    """

    name: ClassVar[str] = "career_analytics"
    input_schema: ClassVar[type[BaseModel]] = CareerAnalyticsInput
    output_schema: ClassVar[type[BaseModel]] = AnalyticsReport

    def run(self, input: CareerAnalyticsInput, ctx: RunContext) -> AgentResult[AnalyticsReport]:
        """Aggregate every tracked application into an ``AnalyticsReport``.

        Args:
            input: Unused (see ``CareerAnalyticsInput``).
            ctx: Run context (repositories; no LLM call is ever made).

        Returns:
            An ``AgentResult`` wrapping the ``AnalyticsReport``.
            ``insufficient_data=True`` is a possible, valid outcome
            (surfaced via ``AgentResult.warnings`` too, not raised).
        """
        start = time.monotonic()
        applications = ctx.repos.applications.list()
        submitted = [a for a in applications if a.status != ApplicationStatus.DRAFTED]

        warnings: list[str] = []
        if len(submitted) < _MIN_APPLICATIONS_FOR_RATES:
            report = AnalyticsReport(
                total_applications=len(applications),
                total_submitted=len(submitted),
                insufficient_data=True,
            )
            warnings.append(
                f"Fewer than {_MIN_APPLICATIONS_FOR_RATES} submitted applications -- "
                "rates withheld as not enough data (agents.md §11 Failure handling)."
            )
        else:
            postings_by_id = {
                posting.id: posting
                for posting in (ctx.repos.jobs.get(a.job_posting_id) for a in submitted)
                if posting is not None
            }
            pairs = [
                (application, postings_by_id[application.job_posting_id])
                for application in submitted
                if application.job_posting_id in postings_by_id
            ]

            response_rate, interview_rate, offer_rate = _rates(submitted)
            report = AnalyticsReport(
                total_applications=len(applications),
                total_submitted=len(submitted),
                insufficient_data=False,
                overall_response_rate=response_rate,
                overall_interview_rate=interview_rate,
                overall_offer_rate=offer_rate,
                by_role_type=_breakdown(pairs, key=lambda posting: posting.title),
                by_source=_breakdown(pairs, key=lambda posting: posting.source),
            )

        latency_ms = int((time.monotonic() - start) * 1000)
        return AgentResult(
            output=report,
            prompt_version="n/a",
            model="n/a",
            latency_ms=latency_ms,
            warnings=warnings,
        )


def _rates(applications: Sequence[Application]) -> tuple[float, float, float]:
    """Response/interview/offer rate for a set of applications, as fractions in [0, 1]."""
    total = len(applications)
    responded = sum(1 for a in applications if a.status in _RESPONDED_STATUSES)
    interviewed = sum(1 for a in applications if a.status in _INTERVIEWED_STATUSES)
    offered = sum(1 for a in applications if a.status == ApplicationStatus.OFFER)
    return responded / total, interviewed / total, offered / total


def _breakdown(
    pairs: Iterable[tuple[Application, JobPosting]], *, key: Callable[[JobPosting], str]
) -> list[RateBreakdown]:
    """Group ``pairs`` by ``key(posting)`` and compute rates per group, sorted by key."""
    groups: dict[str, list[Application]] = {}
    for application, posting in pairs:
        groups.setdefault(key(posting), []).append(application)

    breakdowns = []
    for group_key, group_applications in sorted(groups.items()):
        response_rate, interview_rate, offer_rate = _rates(group_applications)
        breakdowns.append(
            RateBreakdown(
                key=group_key,
                total_submitted=len(group_applications),
                response_rate=response_rate,
                interview_rate=interview_rate,
                offer_rate=offer_rate,
            )
        )
    return breakdowns
