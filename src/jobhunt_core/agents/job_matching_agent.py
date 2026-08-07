"""Job Matching Agent — CandidateProfile + JobPosting to MatchScore (agents.md §4).

Fourth agent in the core pipeline (architecture.md §3.1): scores
compatibility between a candidate and a specific posting, with a
rationale grounded in both texts.
"""

from __future__ import annotations

import time
from typing import ClassVar

from pydantic import BaseModel, ValidationError

from jobhunt_core.agents.base import AgentResult, RunContext, default_model_for
from jobhunt_core.orchestration.registry import register_agent
from jobhunt_core.prompts.loader import load_prompt, render_prompt
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.match import MatchScore, MatchScoreExtraction
from jobhunt_core.schemas.profile import CandidateProfile

_PROMPT_DOMAIN = "job_matching"
_PROMPT_NAME = "score"

_STRICTER_SUFFIX = (
    "\n\nIMPORTANT: Your previous response did not match the required "
    "schema. Return ONLY the fields score (a number 0-100), "
    "matched_requirements (list of strings), missing_requirements "
    "(list of strings), red_flags (list of strings), and rationale "
    "(a string) -- no extra fields, no missing fields, correct types."
)


class JobMatchingInput(BaseModel):
    """Input to the Job Matching Agent (agents.md §4)."""

    candidate_profile: CandidateProfile
    job_posting: JobPosting


@register_agent("job_matching")
class JobMatchingAgent:
    """Scores a ``CandidateProfile`` against a ``JobPosting`` with rationale.

    Never returns a bare score (design.md §2) -- ``MatchScoreExtraction.
    rationale`` is a required field, so a response missing it fails
    schema validation rather than shipping a scoreless-of-context
    result.
    """

    name: ClassVar[str] = "job_matching"
    input_schema: ClassVar[type[BaseModel]] = JobMatchingInput
    output_schema: ClassVar[type[BaseModel]] = MatchScore

    def run(self, input: JobMatchingInput, ctx: RunContext) -> AgentResult[MatchScore]:
        """Score ``input.job_posting`` against ``input.candidate_profile``.

        Args:
            input: The candidate profile and posting to compare.
            ctx: Run context (LLM provider, settings, repositories).

        Returns:
            An ``AgentResult`` wrapping the ``MatchScore``.

        Raises:
            ValidationError: The LLM's response failed schema
                validation twice in a row (once on the initial ask,
                once on the stricter re-ask) -- never silently
                returned as a partially-parsed score (agents.md §4
                Failure handling).
        """
        job_posting_id = input.job_posting.id
        profile_id = input.candidate_profile.id
        if job_posting_id is None or profile_id is None:
            raise ValueError(
                "JobMatchingAgent requires an already-persisted JobPosting and "
                "CandidateProfile (agents.md §4 reads job_postings/candidate_profiles) "
                "-- got one with id=None."
            )

        start = time.monotonic()
        model = default_model_for(self.name, ctx)

        template = load_prompt(_PROMPT_DOMAIN, _PROMPT_NAME)
        prompt = render_prompt(
            template,
            candidate_profile_json=input.candidate_profile.model_dump_json(),
            posting_text=input.job_posting.normalized_description,
        )

        try:
            response = ctx.llm.complete_structured(
                prompt, model=model, response_schema=MatchScoreExtraction, temperature=0.0
            )
        except ValidationError:
            # Shared LLM retry (design.md §11) already covers transient
            # transport errors inside the provider adapter -- this is a
            # second, schema-validation-specific re-ask (agents.md §4
            # Retry logic), not a duplicate of that policy.
            response = ctx.llm.complete_structured(
                prompt + _STRICTER_SUFFIX,
                model=model,
                response_schema=MatchScoreExtraction,
                temperature=0.0,
            )

        match_score = MatchScore(
            job_posting_id=job_posting_id,
            profile_id=profile_id,
            **response.parsed.model_dump(),
        )

        latency_ms = int((time.monotonic() - start) * 1000)
        return AgentResult(
            output=match_score,
            prompt_version=template.version,
            model=model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_estimate_usd=response.cost_estimate_usd,
            latency_ms=latency_ms,
        )
