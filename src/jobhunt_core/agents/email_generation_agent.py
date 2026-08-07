"""Email Generation Agent — JobPosting + ResumeVersion + CoverLetter to EmailDraft.

agents.md §8. Eighth agent in the core pipeline (architecture.md
§3.1). Note: tasks.md T13.1 names this module ``email_agent.py``, but
every other agent module is named after its registered agent name
(``resume_customization_agent.py`` for "resume_customization",
``ats_optimization_agent.py`` for "ats_optimization") -- ``config/
agents.yaml`` and agents.md §8's own header both use
"email_generation", so this module follows that established naming
convention instead; a doc gap in tasks.md's file list, not a
deviation from agents.md.

Single LLM call, no drafter->reviewer loop (agents.md §8 Retry logic:
"Shared LLM retry policy only") -- unlike Resume Customization/Cover
Letter, this agent never introduces new claims about the candidate; it
only summarizes/references two already-approved, already-reviewed
documents, so the sharpest fabrication risk (rules.md AI Coding Rule 1)
is already behind those agents, not ahead of this one.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from jobhunt_core.agents.base import AgentResult, RunContext, default_model_for
from jobhunt_core.orchestration.registry import register_agent
from jobhunt_core.prompts.loader import load_prompt, render_prompt
from jobhunt_core.schemas.document import CoverLetter, ResumeVersion
from jobhunt_core.schemas.email import EmailDraft, EmailDraftExtraction
from jobhunt_core.schemas.job import JobPosting

_PROMPT_DOMAIN = "email"
_PROMPT_NAME = "draft"


class EmailGenerationInput(BaseModel):
    """Input to the Email Generation Agent (agents.md §8)."""

    job_posting: JobPosting
    resume_version: ResumeVersion
    cover_letter: CoverLetter


@register_agent("email_generation")
class EmailGenerationAgent:
    """Drafts the application submission email -- never sends it (PRD.md §9).

    Writes nothing persisted independently in v1 (agents.md §8
    Memory): the draft is surfaced at review time, and once approved
    its content is folded into the ``applications`` row's audit trail
    once Application Tracking (Phase 14) exists.
    """

    name: ClassVar[str] = "email_generation"
    input_schema: ClassVar[type[BaseModel]] = EmailGenerationInput
    output_schema: ClassVar[type[BaseModel]] = EmailDraft

    def run(self, input: EmailGenerationInput, ctx: RunContext) -> AgentResult[EmailDraft]:
        """Draft the application submission email for an already-tailored package.

        Args:
            input: The target posting and its already-approved
                tailored resume and cover letter.
            ctx: Run context (LLM provider, settings, repositories).

        Returns:
            An ``AgentResult`` wrapping the ``EmailDraft``. A missing
            recipient address is a possible, valid outcome (``to=
            None``, surfaced via ``AgentResult.warnings``, never
            raised or guessed -- agents.md §8 Failure handling).

        Raises:
            ValueError: The resume version or cover letter doesn't
                belong to the given job posting.
        """
        start = time.monotonic()
        job_posting_id = input.job_posting.id
        if job_posting_id is not None:
            if input.resume_version.job_posting_id not in (job_posting_id, None):
                raise ValueError(
                    "ResumeVersion.job_posting_id does not match the given JobPosting."
                )
            if input.cover_letter.job_posting_id != job_posting_id:
                raise ValueError("CoverLetter.job_posting_id does not match the given JobPosting.")

        model = default_model_for(self.name, ctx)
        template = load_prompt(_PROMPT_DOMAIN, _PROMPT_NAME)
        prompt = render_prompt(
            template,
            job_title=input.job_posting.title,
            posting_text=input.job_posting.normalized_description,
        )
        response = ctx.llm.complete_structured(
            prompt, model=model, response_schema=EmailDraftExtraction, temperature=0.0
        )
        extraction = response.parsed

        warnings: list[str] = []
        if extraction.to is None:
            warnings.append(
                "No recipient email address found in the posting text -- 'to' is null "
                "rather than guessed (agents.md §8 Failure handling)."
            )

        email_draft = EmailDraft(
            to=extraction.to,
            subject=extraction.subject,
            body=extraction.body,
            attachments=[
                Path(input.resume_version.rendered_pdf_path),
                Path(input.cover_letter.rendered_pdf_path),
            ],
        )

        latency_ms = int((time.monotonic() - start) * 1000)
        return AgentResult(
            output=email_draft,
            prompt_version=template.version,
            model=model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_estimate_usd=response.cost_estimate_usd,
            latency_ms=latency_ms,
            warnings=warnings,
        )
