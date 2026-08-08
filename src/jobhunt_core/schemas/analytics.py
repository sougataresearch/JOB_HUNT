"""Analytics schemas (agents.md §11, database.md §18).

``AnalyticsReport`` is computed on read, never persisted as its own
table (database.md §18) -- these schemas exist purely as the agent's
in-memory/CLI output shape.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RateBreakdown(BaseModel):
    """Response/interview/offer rates for one group (a role title or a source)."""

    key: str
    total_submitted: int
    response_rate: float
    interview_rate: float
    offer_rate: float


class AnalyticsReport(BaseModel):
    """Career Analytics Agent output (agents.md §11, database.md §18).

    ``insufficient_data`` is set when fewer than 5 applications have
    been submitted (agents.md §11 Failure handling's own example
    threshold) -- when true, every rate field stays ``None`` rather
    than showing a rate computed from a handful of data points
    presented as if it meant something (agents.md §11: "rather than
    misleading rates from a tiny sample").

    "Response" = the employer took some visible action beyond silence
    (``screening``/``interview_scheduled``/``interview_completed``/
    ``offer``/``rejected``). Excludes ``withdrawn`` (candidate-
    initiated, not an employer response) and ``submitted`` (no
    response yet) -- agents.md §11 names "response rate" without
    defining which statuses count as a response; this is this
    implementation's own judgment call (rules.md AI Coding Rule 5).
    """

    total_applications: int
    total_submitted: int
    insufficient_data: bool
    overall_response_rate: float | None = None
    overall_interview_rate: float | None = None
    overall_offer_rate: float | None = None
    by_role_type: list[RateBreakdown] = Field(default_factory=list)
    by_source: list[RateBreakdown] = Field(default_factory=list)
