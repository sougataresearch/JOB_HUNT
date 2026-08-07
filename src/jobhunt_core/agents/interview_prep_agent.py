"""Interview Prep Agent — Application/JobPosting/ResumeVersion/MatchScore to InterviewPrepPack.

agents.md §10. Tenth agent in the core pipeline (architecture.md
§3.1). Triggered by the orchestrator watching for
``Application.status == "interview_scheduled"`` transitions in
principle (agents.md §10 Communication protocol); since no
event-driven orchestrator exists yet (`AgentResult`'s own docstring:
"the CLI calls agents directly for now"), that trigger condition is
instead enforced explicitly by ``cli/commands/interview.py`` before
this agent ever runs.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from jobhunt_core.agents.base import AgentResult, RunContext, default_model_for
from jobhunt_core.orchestration.registry import register_agent
from jobhunt_core.prompts.loader import load_prompt, render_prompt
from jobhunt_core.schemas.application import Application
from jobhunt_core.schemas.document import ResumeVersion
from jobhunt_core.schemas.interview import (
    Interview,
    InterviewPrepExtraction,
    InterviewPrepPack,
    InterviewQuestion,
    InterviewType,
)
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.match import MatchScore

_PROMPT_DOMAIN = "interview"
_PROMPT_NAME = "prepare"
_MIN_GROUNDING_CHARS = 200
# agents.md §10 Failure handling names "posting text very short" as
# its example of insufficient grounding data -- 200 chars is this
# implementation's own threshold, not a value drawn from any doc (same
# disclosed-choice pattern as CoverLetterAgent's _MIN_POSTING_DETAILS).
_GROUNDING_NOTE = (
    "The posting text is very short -- prefer general-category questions "
    "and do not invent posting-specific specifics you cannot support."
)


class InterviewPrepInput(BaseModel):
    """Input to the Interview Prep Agent (agents.md §10)."""

    application: Application
    job_posting: JobPosting
    resume_version: ResumeVersion
    match_score: MatchScore
    interview_type: InterviewType
    scheduled_at: datetime | None = None


@register_agent("interview_prep")
class InterviewPrepAgent:
    """Generates categorized interview questions with resume/posting-traceable talking points.

    Never fabricates specifics when grounding data is thin (agents.md
    §10 Failure handling): a short posting text triggers an explicit
    drafter instruction to fall back to general-category questions,
    surfaced to the caller via ``AgentResult.warnings`` -- no schema
    field for this exists on ``InterviewQuestion`` (database.md §12
    defines none), the same no-new-field precedent
    ``ATSOptimizationAgent`` already established for an equivalent
    low-confidence signal.
    """

    name: ClassVar[str] = "interview_prep"
    input_schema: ClassVar[type[BaseModel]] = InterviewPrepInput
    output_schema: ClassVar[type[BaseModel]] = InterviewPrepPack

    def run(self, input: InterviewPrepInput, ctx: RunContext) -> AgentResult[InterviewPrepPack]:
        """Draft and persist a set of interview questions for a scheduled interview.

        Args:
            input: The application, posting, tailored resume, match
                score, and interview type to prepare for.
            ctx: Run context (LLM provider, settings, repositories).

        Returns:
            An ``AgentResult`` wrapping the persisted ``InterviewPrepPack``.
            Thin grounding data is a possible, valid outcome (surfaced
            via ``AgentResult.warnings``, not raised).

        Raises:
            ValueError: The application isn't persisted yet, or the
                given posting/resume version/match score don't belong
                to the same application.
        """
        start = time.monotonic()
        application_id = input.application.id
        job_posting_id = input.job_posting.id
        if application_id is None or job_posting_id is None:
            raise ValueError(
                "InterviewPrepAgent requires an already-persisted Application and "
                "JobPosting (agents.md §10 reads applications/job_postings) -- got "
                "one with id=None."
            )
        if input.application.job_posting_id != job_posting_id:
            raise ValueError("Application.job_posting_id does not match the given JobPosting.")
        if input.resume_version.job_posting_id not in (job_posting_id, None):
            raise ValueError("ResumeVersion.job_posting_id does not match the given JobPosting.")
        if input.match_score.job_posting_id != job_posting_id:
            raise ValueError("MatchScore.job_posting_id does not match the given JobPosting.")

        posting_text = input.job_posting.normalized_description
        resume_text = Path(input.resume_version.ats_extracted_text_path).read_text(encoding="utf-8")
        low_grounding = len(posting_text.strip()) < _MIN_GROUNDING_CHARS

        model = default_model_for(self.name, ctx)
        template = load_prompt(_PROMPT_DOMAIN, _PROMPT_NAME)
        prompt = render_prompt(
            template,
            posting_text=posting_text,
            resume_text=resume_text,
            match_score_json=input.match_score.model_dump_json(),
            interview_type=input.interview_type.value,
            grounding_note=_GROUNDING_NOTE if low_grounding else "",
        )
        response = ctx.llm.complete_structured(
            prompt, model=model, response_schema=InterviewPrepExtraction, temperature=0.0
        )

        interview = ctx.repos.interviews.save(
            Interview(
                application_id=application_id,
                scheduled_at=input.scheduled_at,
                interview_type=input.interview_type,
            )
        )
        questions = [
            ctx.repos.interviews.add_question(
                InterviewQuestion(
                    interview_id=interview.id or "",
                    category=draft.category,
                    question=draft.question,
                    suggested_talking_points=draft.suggested_talking_points,
                )
            )
            for draft in response.parsed.questions
        ]

        warnings: list[str] = []
        if low_grounding:
            warnings.append(
                "Posting text is very short; questions are general-category and "
                "less-grounded (agents.md §10 Failure handling)."
            )
        if not questions:
            warnings.append("No interview questions were generated.")

        latency_ms = int((time.monotonic() - start) * 1000)
        return AgentResult(
            output=InterviewPrepPack(interview=interview, questions=questions),
            prompt_version=template.version,
            model=model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_estimate_usd=response.cost_estimate_usd,
            latency_ms=latency_ms,
            warnings=warnings,
        )
