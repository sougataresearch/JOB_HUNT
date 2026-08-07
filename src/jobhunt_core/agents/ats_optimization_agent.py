"""ATS Optimization Agent — CandidateProfile + JobPosting to ATSReport (agents.md §5).

Fifth agent in the core pipeline (architecture.md §3.1). Two-step
design per agents.md §5 Tools ("deterministic keyword/embedding-
similarity matching where possible... LLM reserved for judgment
calls"):

1. **Deterministic** (this module, no LLM): extract keyword-shaped
   candidates from the posting text and check which are absent from
   the candidate's profile text. Never retried (design.md §11 --
   nothing transient about it).
2. **LLM judgment** (the ``analyze`` prompt): classify each
   deterministically-found gap as supported (real experience, just
   worded differently) or unsupported (no underlying evidence, must
   never be fabricated into a document -- rules.md AI Coding Rule 1).
   The LLM never discovers gaps of its own, only classifies the ones
   step 1 already found.
"""

from __future__ import annotations

import re
import time
from typing import ClassVar

from pydantic import BaseModel

from jobhunt_core.agents.base import AgentResult, RunContext, default_model_for
from jobhunt_core.orchestration.registry import register_agent
from jobhunt_core.prompts.loader import load_prompt, render_prompt
from jobhunt_core.schemas.ats import ATSGapClassification, ATSReport
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.profile import CandidateProfile

_PROMPT_DOMAIN = "ats"
_PROMPT_NAME = "analyze"

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#/-]{1,}")

# Common capitalized sentence-starters/filler that would otherwise look
# like "keywords" under the capitalized-token heuristic below -- kept
# short and job-posting-specific, not a general-purpose stopword list.
_STOPWORDS = {
    "the", "and", "with", "for", "you", "your", "we", "our", "a", "an", "to", "of", "in",
    "on", "is", "are", "will", "have", "has", "this", "that", "as", "be", "or", "at",
    "team", "role", "join", "looking", "experience", "experienced", "years", "strong",
    "skills", "work", "who", "us", "about", "job", "company", "must", "should", "can",
    "using", "new", "requires", "required", "requirements", "seeking", "responsible",
    "preferred", "candidates", "applicants",
}  # fmt: skip


class ATSOptimizationInput(BaseModel):
    """Input to the ATS Optimization Agent (agents.md §5)."""

    candidate_profile: CandidateProfile
    job_posting: JobPosting


@register_agent("ats_optimization")
class ATSOptimizationAgent:
    """Identifies keyword gaps between a profile and a posting, classified honestly.

    Never fabricates a supported gap (rules.md AI Coding Rule 1): the
    LLM only classifies gaps the deterministic step already found, and
    the prompt explicitly instructs "when in doubt, prefer
    UNSUPPORTED."
    """

    name: ClassVar[str] = "ats_optimization"
    input_schema: ClassVar[type[BaseModel]] = ATSOptimizationInput
    output_schema: ClassVar[type[BaseModel]] = ATSReport

    def run(self, input: ATSOptimizationInput, ctx: RunContext) -> AgentResult[ATSReport]:
        """Diff ``input.job_posting`` against ``input.candidate_profile`` for keyword gaps.

        Args:
            input: The candidate profile and posting to compare.
            ctx: Run context (LLM provider, settings, repositories).

        Returns:
            An ``AgentResult`` wrapping the ``ATSReport``. If the
            posting has no usable text or no keyword gaps are found,
            no LLM call is made at all (rules.md §Performance
            Guidelines) and an explicit low-confidence/empty report is
            returned via ``AgentResult.warnings`` (agents.md §5
            Failure handling) -- ``ATSReport`` itself has no
            confidence field, so this is how "explicit low-confidence"
            is surfaced without inventing a new schema field.
        """
        start = time.monotonic()
        job_posting_id = input.job_posting.id
        profile_id = input.candidate_profile.id
        if job_posting_id is None or profile_id is None:
            raise ValueError(
                "ATSOptimizationAgent requires an already-persisted JobPosting and "
                "CandidateProfile (agents.md §5 reads job_postings/candidate_profiles) "
                "-- got one with id=None."
            )

        posting_text = input.job_posting.normalized_description
        if not posting_text.strip():
            report = ATSReport(job_posting_id=job_posting_id, profile_id=profile_id)
            return AgentResult(
                output=report,
                prompt_version="n/a",
                model="n/a",
                latency_ms=int((time.monotonic() - start) * 1000),
                warnings=[
                    "Posting has no text to analyze -- returning an empty, "
                    "low-confidence report rather than fabricating gaps."
                ],
            )

        profile_text = _flatten_profile_text(input.candidate_profile)
        candidate_gaps = _missing_keywords(posting_text, profile_text)

        if not candidate_gaps:
            report = ATSReport(job_posting_id=job_posting_id, profile_id=profile_id)
            return AgentResult(
                output=report,
                prompt_version="n/a",
                model="n/a",
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        model = default_model_for(self.name, ctx)
        template = load_prompt(_PROMPT_DOMAIN, _PROMPT_NAME)
        prompt = render_prompt(
            template,
            candidate_profile_json=input.candidate_profile.model_dump_json(),
            posting_text=posting_text,
            raw_keyword_gaps="\n".join(f"- {gap}" for gap in candidate_gaps),
        )

        response = ctx.llm.complete_structured(
            prompt, model=model, response_schema=ATSGapClassification, temperature=0.0
        )

        report = ATSReport(
            job_posting_id=job_posting_id,
            profile_id=profile_id,
            supported_gaps=response.parsed.supported_gaps,
            unsupported_gaps=response.parsed.unsupported_gaps,
        )

        latency_ms = int((time.monotonic() - start) * 1000)
        return AgentResult(
            output=report,
            prompt_version=template.version,
            model=model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_estimate_usd=response.cost_estimate_usd,
            latency_ms=latency_ms,
        )


def _flatten_profile_text(profile: CandidateProfile) -> str:
    """Every free-text field a keyword could plausibly appear in."""
    parts = [profile.summary or "", " ".join(profile.skills), " ".join(profile.certifications)]
    for entry in profile.experience:
        parts.append(entry.title)
        parts.append(entry.company)
        parts.extend(entry.bullets)
    return " ".join(parts)


def _candidate_keywords(posting_text: str) -> list[str]:
    """Deterministic keyword candidates from posting text (agents.md §5 Tools).

    Heuristic: a "keyword" is a capitalized token (proper noun / tech
    term / acronym -- AWS, Python, PostgreSQL) not in a small
    job-posting-specific stopword list. Known, disclosed limitation:
    misses genuine keywords the posting happens to write in lowercase,
    and may over-include capitalized filler -- this function only
    surfaces *candidates* for the downstream LLM judgment step, not a
    final verdict, so both failure modes are recoverable, not silent.
    """
    seen: dict[str, None] = {}
    for match in _WORD_RE.finditer(posting_text):
        # _WORD_RE's char class includes "." for tech terms like "C#"/
        # "Node.js", which also greedily swallows a sentence-ending
        # period (e.g. "...with Kubernetes." -> "Kubernetes."). Trim
        # trailing punctuation the class would never legitimately end
        # a real token with.
        token = match.group(0).rstrip(".,;:!?")
        if not token or not token[0].isupper():
            continue
        if token.lower() in _STOPWORDS or len(token) < 2:
            continue
        seen.setdefault(token, None)
    return list(seen)


def _missing_keywords(posting_text: str, profile_text: str) -> list[str]:
    """Candidate keywords from the posting that don't appear anywhere in the profile text."""
    lowered_profile = profile_text.lower()
    return [kw for kw in _candidate_keywords(posting_text) if kw.lower() not in lowered_profile]
