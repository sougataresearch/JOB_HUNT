"""Cover Letter Agent — CandidateProfile + JobPosting + ResumeVersion to CoverLetter.

agents.md §7, decisions.md ADR-0007. Seventh agent in the core pipeline
(architecture.md §3.1): draft -> review -> (one redraft on rejection)
-> render -> compile -> persist. Same drafter->reviewer + recompile
policy as Resume Customization Agent (agents.md §7 Retry logic:
"Same pattern as Resume Customization Agent"), reusing the shared
``DocumentRenderer`` (agents.md §7 Tools) but not the PDF-text
verification step -- see schemas/document.py's ``CoverLetter``
docstring for why.
"""

from __future__ import annotations

import re
import time
import uuid
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from jobhunt_core.agents.base import AgentResult, RunContext, default_model_for
from jobhunt_core.documents.renderer import get_renderer_class
from jobhunt_core.errors import RenderError
from jobhunt_core.orchestration.registry import register_agent
from jobhunt_core.prompts.loader import PromptTemplate, load_prompt, render_prompt
from jobhunt_core.schemas.document import (
    CoverLetter,
    CoverLetterDraft,
    ResumeVersion,
    ReviewVerdict,
)
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.profile import CandidateProfile

_PROMPT_DOMAIN = "cover_letter"
_DRAFT_PROMPT = "draft"
_REVIEW_PROMPT = "review"
_TEMPLATE_KIND = "cover_letter"
_TEMPLATE_NAME = "cover_letter"
_TEMPLATE_RELATIVE_PATH = "cover_letter/cover_letter.tex.jinja"
_RENDERER_KIND = "latex"
_MAX_REDRAFTS = 1
# agents.md §7 Retry logic: "Same pattern as Resume Customization Agent
# (shared drafter->reviewer + recompile policy)" -- one automatic
# redraft on reviewer rejection, no further automatic retries.

_MIN_POSTING_DETAILS = 3
# phases.md Phase 12 AC: "references at least N concrete details from
# the posting (checked via a simple keyword-presence eval, not just
# vibes)". N is not specified anywhere in the docs -- 3 is this
# implementation's chosen threshold, not a value drawn from any spec.
_DETAIL_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#/-]{2,}")
_DETAIL_STOPWORDS = {
    "the", "and", "with", "for", "you", "your", "we", "our", "this", "that", "are",
    "will", "have", "has", "from", "about", "team", "role", "join", "looking",
    "experience", "years", "strong", "skills", "work", "who", "job", "company",
    "must", "should", "can", "using", "new", "required", "requirements", "seeking",
    "preferred", "candidates", "applicants", "full", "time", "part",
}  # fmt: skip

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = REPO_ROOT / "documents" / "templates"


class CoverLetterInput(BaseModel):
    """Input to the Cover Letter Agent (agents.md §7)."""

    candidate_profile: CandidateProfile
    job_posting: JobPosting
    resume_version: ResumeVersion


@register_agent("cover_letter")
class CoverLetterAgent:
    """Produces a tailored, compiled cover letter for a specific posting.

    Never fabricates content (rules.md AI Coding Rule 1): the drafter
    only writes prose grounded in the candidate profile and the
    already-approved tailored resume text (read from ``ResumeVersion.
    ats_extracted_text_path``, reusing Phase 11's PDF-verification
    artifact rather than re-deriving resume content independently), and
    a reviewer pass -- fresh context, checking both fabrication and
    contradiction with the resume -- must approve before anything is
    rendered, with exactly one automatic redraft on rejection.
    """

    name: ClassVar[str] = "cover_letter"
    input_schema: ClassVar[type[BaseModel]] = CoverLetterInput
    output_schema: ClassVar[type[BaseModel]] = CoverLetter

    def run(self, input: CoverLetterInput, ctx: RunContext) -> AgentResult[CoverLetter]:
        """Draft, review, render, and compile a tailored cover letter PDF.

        Args:
            input: Candidate profile, target posting, and the already
                -approved tailored resume for the same posting.
            ctx: Run context (LLM provider, settings, repositories).

        Returns:
            An ``AgentResult`` wrapping the persisted ``CoverLetter``.
            A letter referencing fewer than ``_MIN_POSTING_DETAILS``
            distinct posting-derived words is a possible, valid outcome
            (surfaced via ``AgentResult.warnings``, not raised) --
            design.md's "fail loud to the user, fail soft to the
            pipeline."

        Raises:
            ValueError: The profile, posting, or resume version isn't
                persisted yet, or the resume version doesn't belong to
                this profile/posting pair.
            RenderError: The draft was rejected twice (once initially,
                once after the automatic redraft) and never approved,
                or LaTeX compilation itself failed.
        """
        start = time.monotonic()
        profile_id = input.candidate_profile.id
        job_posting_id = input.job_posting.id
        resume_version_id = input.resume_version.id
        if profile_id is None or job_posting_id is None or resume_version_id is None:
            raise ValueError(
                "CoverLetterAgent requires an already-persisted JobPosting, "
                "CandidateProfile, and ResumeVersion (agents.md §7 reads job_postings/"
                "candidate_profiles/resume_versions) -- got one with id=None."
            )
        if input.resume_version.profile_id != profile_id:
            raise ValueError("ResumeVersion.profile_id does not match the given CandidateProfile.")
        if input.resume_version.job_posting_id not in (job_posting_id, None):
            raise ValueError("ResumeVersion.job_posting_id does not match the given JobPosting.")

        resume_text = Path(input.resume_version.ats_extracted_text_path).read_text(encoding="utf-8")

        model = default_model_for(self.name, ctx)
        draft_template = load_prompt(_PROMPT_DOMAIN, _DRAFT_PROMPT)
        review_template = load_prompt(_PROMPT_DOMAIN, _REVIEW_PROMPT)
        candidate_profile_json = input.candidate_profile.model_dump_json()
        posting_text = input.job_posting.normalized_description

        draft, review, redraft_count = self._draft_and_review(
            ctx=ctx,
            model=model,
            draft_template=draft_template,
            review_template=review_template,
            candidate_profile_json=candidate_profile_json,
            posting_text=posting_text,
            resume_text=resume_text,
        )

        if not review.approved:
            raise RenderError(
                f"Cover letter draft was rejected after {redraft_count} redraft(s): "
                f"{review.feedback}",
                remedy="Review the feedback above; the draft/review prompts may need a "
                "fix, or the profile may lack content relevant to this posting.",
            )

        render_context = _build_render_context(input.candidate_profile, draft)

        renderer_cls = get_renderer_class(_RENDERER_KIND)
        renderer = renderer_cls()
        template_source = (TEMPLATES_DIR / _TEMPLATE_RELATIVE_PATH).read_text(encoding="utf-8")
        tex_source = renderer.render(template_source, render_context)

        template = ctx.repos.documents.get_or_create_template(
            kind=_TEMPLATE_KIND, name=_TEMPLATE_NAME, file_path=_TEMPLATE_RELATIVE_PATH
        )
        output_dir = ctx.settings.data_dir / "documents" / "cover_letters" / str(uuid.uuid4())
        pdf_path = renderer.compile(tex_source, output_dir, base_name="cover_letter")

        cover_letter = CoverLetter(
            job_posting_id=job_posting_id,
            resume_version_id=resume_version_id,
            template_id=template.id or "",
            rendered_pdf_path=str(pdf_path),
            rendered_tex_path=str(output_dir / "cover_letter.tex"),
        )
        saved = ctx.repos.documents.save_cover_letter(cover_letter)

        warnings: list[str] = []
        if redraft_count:
            warnings.append(
                f"Initial draft was rejected and redrafted {redraft_count} time(s) "
                f"before approval: {review.feedback}"
            )
        letter_text = " ".join([draft.salutation, *draft.paragraphs, draft.sign_off])
        detail_words = _posting_detail_words(input.job_posting)
        referenced = _count_referenced_details(letter_text, detail_words)
        if referenced < _MIN_POSTING_DETAILS:
            warnings.append(
                f"Cover letter references only {referenced} concrete posting detail(s) "
                f"(want >= {_MIN_POSTING_DETAILS}); it may read as generic."
            )

        latency_ms = int((time.monotonic() - start) * 1000)
        return AgentResult(
            output=saved,
            prompt_version=draft_template.version,
            model=model,
            latency_ms=latency_ms,
            warnings=warnings,
        )

    def _draft_and_review(
        self,
        *,
        ctx: RunContext,
        model: str,
        draft_template: PromptTemplate,
        review_template: PromptTemplate,
        candidate_profile_json: str,
        posting_text: str,
        resume_text: str,
    ) -> tuple[CoverLetterDraft, ReviewVerdict, int]:
        reviewer_feedback = ""
        draft: CoverLetterDraft
        review: ReviewVerdict
        redraft_count = 0

        for attempt in range(_MAX_REDRAFTS + 1):
            draft_prompt = render_prompt(
                draft_template,
                candidate_profile_json=candidate_profile_json,
                posting_text=posting_text,
                resume_text=resume_text,
                reviewer_feedback=reviewer_feedback,
            )
            draft_response = ctx.llm.complete_structured(
                draft_prompt, model=model, response_schema=CoverLetterDraft, temperature=0.0
            )
            draft = draft_response.parsed

            # Independent, fresh-context call (same reasoning as
            # ResumeCustomizationAgent._draft_and_review): its own prompt
            # reconstructed from the profile/posting/resume/draft, never
            # the drafter's own conversation history.
            review_prompt = render_prompt(
                review_template,
                candidate_profile_json=candidate_profile_json,
                posting_text=posting_text,
                resume_text=resume_text,
                draft_content=draft.model_dump_json(),
            )
            review_response = ctx.llm.complete_structured(
                review_prompt, model=model, response_schema=ReviewVerdict, temperature=0.0
            )
            review = review_response.parsed

            if review.approved:
                return draft, review, redraft_count
            if attempt < _MAX_REDRAFTS:
                redraft_count += 1
                reviewer_feedback = review.feedback

        return draft, review, redraft_count


def _build_render_context(profile: CandidateProfile, draft: CoverLetterDraft) -> dict[str, object]:
    """Assemble the LaTeX template's data context.

    Name/email/phone/location come straight from ``CandidateProfile``
    (never LLM-touched); salutation/paragraphs/sign_off come from the
    reviewed ``CoverLetterDraft``.
    """
    return {
        "full_name": profile.full_name or "",
        "email": profile.email,
        "phone": profile.phone,
        "location": profile.location,
        "salutation": draft.salutation,
        "paragraphs": draft.paragraphs,
        "sign_off": draft.sign_off,
    }


def _posting_detail_words(job_posting: JobPosting) -> set[str]:
    """Deterministic candidate "concrete detail" words drawn from the posting.

    Heuristic: any word of length >= 4, lowercased, from the posting's
    title + description, excluding generic job-posting filler --
    mirrors ats_optimization_agent.py's keyword-extraction style but is
    a separate, simpler helper (this checks *presence in the letter*,
    not *absence from the profile*, a different purpose).
    """
    text = f"{job_posting.title} {job_posting.normalized_description}"
    words = {match.group(0).rstrip(".,;:!?").lower() for match in _DETAIL_WORD_RE.finditer(text)}
    return {word for word in words if len(word) >= 4 and word not in _DETAIL_STOPWORDS}


def _count_referenced_details(letter_text: str, detail_words: set[str]) -> int:
    """How many of ``detail_words`` appear (case-insensitively) in the letter text."""
    lowered = letter_text.lower()
    return sum(1 for word in detail_words if word in lowered)
