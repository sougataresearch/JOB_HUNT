"""Skill Gap Agent — CandidateProfile + target vs. SkillGapReport (agents.md §2).

Second agent in the core pipeline (architecture.md §3.1): reuses the
Resume Analysis Agent's structure directly (implementation_order.md
step 21), just with a different input/output schema pair and prompt.
"""

from __future__ import annotations

import time
from typing import ClassVar

from pydantic import BaseModel, Field, model_validator

from jobhunt_core.agents.base import AgentResult, RunContext, default_model_for
from jobhunt_core.orchestration.registry import register_agent
from jobhunt_core.prompts.loader import load_prompt, render_prompt
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.profile import CandidateProfile
from jobhunt_core.schemas.skill_gap import SkillGapReport

_PROMPT_DOMAIN = "skill_gap"
_PROMPT_NAME = "analyze"


class SkillGapInput(BaseModel):
    """Input to the Skill Gap Agent (agents.md §2).

    Exactly one of ``target_role``/``postings`` must be given — the
    agent compares the profile against a user-specified target role
    description *or* an aggregate of sourced postings, per agents.md
    §2 Responsibilities; validated here (a system boundary) rather
    than left for the prompt to silently handle an empty target.
    """

    candidate_profile: CandidateProfile
    target_role: str | None = None
    postings: list[JobPosting] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_a_target(self) -> SkillGapInput:
        if not self.target_role and not self.postings:
            raise ValueError(
                "SkillGapInput requires target_role or at least one posting in postings."
            )
        return self


@register_agent("skill_gap")
class SkillGapAgent:
    """Compares a ``CandidateProfile`` against a target role/postings for gaps.

    Never fabricates a gap unconnected to the profile (rules.md AI
    Coding Rule 1) — enforced by the prompt's evidence-or-absence
    instruction and by ``SkillGap.evidence``/``rationale`` being
    required fields, so a response missing either fails schema
    validation rather than shipping a hollow gap.
    """

    name: ClassVar[str] = "skill_gap"
    input_schema: ClassVar[type[BaseModel]] = SkillGapInput
    output_schema: ClassVar[type[BaseModel]] = SkillGapReport

    def run(self, input: SkillGapInput, ctx: RunContext) -> AgentResult[SkillGapReport]:
        """Compare ``input.candidate_profile`` against its target, returning a ``SkillGapReport``.

        Args:
            input: The candidate profile plus target role/postings to compare against.
            ctx: Run context (LLM provider, settings, repositories).

        Returns:
            An ``AgentResult`` wrapping the ``SkillGapReport``.
        """
        start = time.monotonic()

        model = default_model_for(self.name, ctx)

        template = load_prompt(_PROMPT_DOMAIN, _PROMPT_NAME)
        prompt = render_prompt(
            template,
            candidate_profile_json=input.candidate_profile.model_dump_json(),
            target_context=_build_target_context(input),
        )

        response = ctx.llm.complete_structured(prompt, model=model, response_schema=SkillGapReport)

        latency_ms = int((time.monotonic() - start) * 1000)
        return AgentResult(
            output=response.parsed,
            prompt_version=template.version,
            model=model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_estimate_usd=response.cost_estimate_usd,
            latency_ms=latency_ms,
        )


def _build_target_context(input: SkillGapInput) -> str:
    # posting.company_id is a foreign-key id, not a resolved company name
    # (JobPosting doesn't carry Company inline) -- omitted here rather
    # than rendering a meaningless id string into the prompt.
    if input.target_role:
        return input.target_role
    return "\n\n".join(
        f"Title: {posting.title}\nDescription: {posting.normalized_description}"
        for posting in input.postings
    )
