"""Application Tracking Agent — persists and manages the lifecycle of every application.

agents.md §9. Ninth agent in the core pipeline (architecture.md §3.1).
Deterministic, no LLM call at all (agents.md §9 Prompt template:
"None (deterministic agent -- included here for completeness of the
pipeline, not because it calls an LLM)") -- ``prompt_version``/
``model`` are always ``"n/a"``, the same convention
``ATSOptimizationAgent`` already uses for its own no-LLM-call paths.
"""

from __future__ import annotations

import csv
import io
import time
from collections.abc import Sequence
from typing import ClassVar

from pydantic import BaseModel

from jobhunt_core.agents.base import AgentResult, RunContext
from jobhunt_core.orchestration.registry import register_agent
from jobhunt_core.schemas.application import Application, ApplicationStatus
from jobhunt_core.schemas.document import CoverLetter, ResumeVersion
from jobhunt_core.schemas.job import JobPosting

_CSV_FIELDNAMES = [
    "id",
    "job_posting_id",
    "status",
    "resume_version_id",
    "cover_letter_id",
    "source_channel",
    "submitted_at",
    "created_at",
]


class ApplicationTrackingInput(BaseModel):
    """Input to the Application Tracking Agent (agents.md §9).

    Two modes over the same ``job_posting_id``, both handled by
    ``run()``'s single idempotent create-or-transition logic
    (design.md §2): create/register a new application from an
    approved package (``resume_version``/``cover_letter`` set,
    ``status``/``note`` omitted -> defaults to
    ``ApplicationStatus.DRAFTED``), or a later status-update command
    (``status`` set, ``resume_version``/``cover_letter`` omitted). No
    email field -- database.md §9's ``applications`` columns have no
    slot for email content, and ``EmailDraft`` (agents.md §8) is never
    persisted independently.
    """

    job_posting: JobPosting
    resume_version: ResumeVersion | None = None
    cover_letter: CoverLetter | None = None
    status: ApplicationStatus | None = None
    note: str | None = None


@register_agent("application_tracking")
class ApplicationTrackingAgent:
    """Creates/updates ``Application`` rows and appends ``ApplicationEvent`` history.

    Never overwrites status history (design.md §3 "soft state, hard
    history" -- enforced by ``ApplicationRepo.change_status()``, not
    re-implemented here). A duplicate creation attempt for the same
    ``job_posting_id`` returns the existing record rather than erroring
    or duplicating (agents.md §9 Failure handling, already implemented
    by ``ApplicationRepo.create()``'s own idempotency).
    """

    name: ClassVar[str] = "application_tracking"
    input_schema: ClassVar[type[BaseModel]] = ApplicationTrackingInput
    output_schema: ClassVar[type[BaseModel]] = Application

    def run(self, input: ApplicationTrackingInput, ctx: RunContext) -> AgentResult[Application]:
        """Create a new application or record a status transition for an existing one.

        Args:
            input: The target posting, plus either an approved
                resume/cover-letter package (create mode) or a status/
                note (transition mode) -- see ``ApplicationTrackingInput``.
            ctx: Run context (repositories; no LLM call is ever made).

        Returns:
            An ``AgentResult`` wrapping the current ``Application``.
            If an application already exists and neither a new status
            nor document references are being applied, the existing
            record is returned unchanged (idempotent no-op).

        Raises:
            ValueError: The posting isn't persisted yet, or a given
                ``resume_version``/``cover_letter`` doesn't belong to
                this posting.
        """
        start = time.monotonic()
        job_posting_id = input.job_posting.id
        if job_posting_id is None:
            raise ValueError(
                "ApplicationTrackingAgent requires an already-persisted JobPosting "
                "(agents.md §9 reads job_postings) -- got one with id=None."
            )
        if input.resume_version is not None and input.resume_version.job_posting_id not in (
            job_posting_id,
            None,
        ):
            raise ValueError("ResumeVersion.job_posting_id does not match the given JobPosting.")
        if input.cover_letter is not None and input.cover_letter.job_posting_id != job_posting_id:
            raise ValueError("CoverLetter.job_posting_id does not match the given JobPosting.")

        existing = ctx.repos.applications.get_by_job_posting(job_posting_id)
        warnings: list[str] = []

        if existing is None:
            application = Application(
                job_posting_id=job_posting_id,
                resume_version_id=input.resume_version.id if input.resume_version else None,
                cover_letter_id=input.cover_letter.id if input.cover_letter else None,
                status=input.status or ApplicationStatus.DRAFTED,
            )
            saved = ctx.repos.applications.create(application)
        elif input.status is not None and input.status != existing.status:
            assert existing.id is not None  # fetched from the DB, always has an id
            saved = ctx.repos.applications.change_status(existing.id, input.status, note=input.note)
        else:
            saved = existing
            if input.resume_version is not None or input.cover_letter is not None:
                warnings.append(
                    "Application already exists; resume_version/cover_letter references "
                    "are only set at creation and were not updated."
                )

        latency_ms = int((time.monotonic() - start) * 1000)
        return AgentResult(
            output=saved,
            prompt_version="n/a",
            model="n/a",
            latency_ms=latency_ms,
            warnings=warnings,
        )


def export_applications_csv(applications: Sequence[Application]) -> str:
    """Render applications as CSV text (agents.md §9 Tools: "CSV writer").

    One row per application -- a raw export, not pre-aggregated;
    computing response/interview/offer rates from application history
    is Career Analytics Agent's job (agents.md §11), not this one's.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_FIELDNAMES)
    for application in applications:
        writer.writerow(
            [
                application.id or "",
                application.job_posting_id,
                application.status.value,
                application.resume_version_id or "",
                application.cover_letter_id or "",
                application.source_channel or "",
                application.submitted_at.isoformat() if application.submitted_at else "",
                application.created_at.isoformat() if application.created_at else "",
            ]
        )
    return buffer.getvalue()
