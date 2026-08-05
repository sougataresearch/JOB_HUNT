"""Resume Analysis Agent — CV file to CandidateProfile (agents.md §1).

The first agent in the core pipeline (architecture.md §3.1): turns a
raw CV file into a structured, persisted ``CandidateProfile`` that
every downstream agent reads from.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from jobhunt_core.agents.base import AgentResult, RunContext
from jobhunt_core.documents.parsers import parser_for_file
from jobhunt_core.orchestration.registry import register_agent
from jobhunt_core.prompts.loader import load_prompt, render_prompt
from jobhunt_core.schemas.profile import CandidateProfile, CandidateProfileExtraction

_PROMPT_DOMAIN = "resume_analysis"
_PROMPT_NAME = "extract_profile"


class ResumeAnalysisInput(BaseModel):
    """Input to the Resume Analysis Agent."""

    cv_file_path: Path


@register_agent("resume_analysis")
class ResumeAnalysisAgent:
    """Converts a raw CV file into a structured ``CandidateProfile``.

    Never invents a field the CV doesn't support (rules.md AI Coding
    Rule 1) -- enforced by the prompt's no-fabrication instruction and
    by every field in ``CandidateProfileExtraction`` being optional, so
    "not found" is always a legitimate, representable answer.
    """

    name: ClassVar[str] = "resume_analysis"
    input_schema: ClassVar[type[BaseModel]] = ResumeAnalysisInput
    output_schema: ClassVar[type[BaseModel]] = CandidateProfile

    def run(self, input: ResumeAnalysisInput, ctx: RunContext) -> AgentResult[CandidateProfile]:
        """Parse ``input.cv_file_path`` and extract a ``CandidateProfile``.

        Args:
            input: The CV file to analyze.
            ctx: Run context (LLM provider, settings, repositories).

        Returns:
            An ``AgentResult`` wrapping the extracted ``CandidateProfile``.
        """
        start = time.monotonic()

        parser = parser_for_file(input.cv_file_path)
        parsed = parser.parse(input.cv_file_path)

        agent_cfg = ctx.settings.agents.get(self.name)
        model = (agent_cfg.model if agent_cfg else None) or _default_model(ctx)

        template = load_prompt(_PROMPT_DOMAIN, _PROMPT_NAME)
        prompt = render_prompt(template, cv_raw_text=parsed.raw_text)

        response = ctx.llm.complete_structured(
            prompt, model=model, response_schema=CandidateProfileExtraction
        )
        profile = CandidateProfile(
            source_file_path=str(input.cv_file_path),
            **response.parsed.model_dump(),
        )

        latency_ms = int((time.monotonic() - start) * 1000)
        return AgentResult(
            output=profile,
            prompt_version=template.version,
            model=model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_estimate_usd=response.cost_estimate_usd,
            latency_ms=latency_ms,
        )


def _default_model(ctx: RunContext) -> str:
    provider_cfg = ctx.settings.llm.providers.get(ctx.settings.llm.default_provider)
    return provider_cfg.base_model if provider_cfg else ctx.settings.llm.default_provider
