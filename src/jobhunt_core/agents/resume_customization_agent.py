"""Resume Customization Agent — CandidateProfile + JobPosting + ATSReport to ResumeVersion.

agents.md §6, decisions.md ADR-0007. Sixth agent in the core pipeline
(architecture.md §3.1): draft -> review -> (one redraft on rejection)
-> render -> compile -> verify -> persist.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from jobhunt_core.agents.base import AgentResult, RunContext, default_model_for
from jobhunt_core.documents.renderer import get_renderer_class
from jobhunt_core.documents.verify import verify_pdf_text
from jobhunt_core.errors import RenderError
from jobhunt_core.orchestration.registry import register_agent
from jobhunt_core.prompts.loader import PromptTemplate, load_prompt, render_prompt
from jobhunt_core.schemas.ats import ATSReport
from jobhunt_core.schemas.document import ResumeDraft, ResumeVersion, ReviewVerdict
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.profile import CandidateProfile

_PROMPT_DOMAIN = "resume_customization"
_DRAFT_PROMPT = "draft"
_REVIEW_PROMPT = "review"
_TEMPLATE_KIND = "resume"
_TEMPLATE_NAME = "resume"
_TEMPLATE_RELATIVE_PATH = "cv/resume.tex.jinja"
_RENDERER_KIND = "latex"
_MAX_REDRAFTS = 1
# agents.md §6 Retry logic: "One automatic redraft on reviewer rejection --
# no further automatic retries."

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = REPO_ROOT / "documents" / "templates"


class ResumeCustomizationInput(BaseModel):
    """Input to the Resume Customization Agent (agents.md §6)."""

    candidate_profile: CandidateProfile
    job_posting: JobPosting
    ats_report: ATSReport


@register_agent("resume_customization")
class ResumeCustomizationAgent:
    """Produces a tailored, compiled, ATS-verified CV PDF for a specific posting.

    Never fabricates content (rules.md AI Coding Rule 1): the drafter
    only selects/rewords/trims the candidate's real experience (never
    touches name/contact/education, pulled from ``CandidateProfile``
    unchanged by the renderer instead), and a reviewer pass -- on a
    fresh, independent prompt, not the drafter's own conversation --
    must approve before anything is rendered, with exactly one
    automatic redraft on rejection before surfacing to the caller.
    """

    name: ClassVar[str] = "resume_customization"
    input_schema: ClassVar[type[BaseModel]] = ResumeCustomizationInput
    output_schema: ClassVar[type[BaseModel]] = ResumeVersion

    def run(self, input: ResumeCustomizationInput, ctx: RunContext) -> AgentResult[ResumeVersion]:
        """Draft, review, render, compile, and verify a tailored resume PDF.

        Args:
            input: Candidate profile, target posting, and its ATS report.
            ctx: Run context (LLM provider, settings, repositories).

        Returns:
            An ``AgentResult`` wrapping the persisted ``ResumeVersion``.
            ``ats_verification_passed=False`` is a possible, valid
            outcome (surfaced via ``AgentResult.warnings``, not raised)
            -- design.md's "fail loud to the user, fail soft to the
            pipeline" -- the caller decides whether to accept it.

        Raises:
            ValueError: The profile or posting isn't persisted yet.
            RenderError: The draft was rejected twice (once initially,
                once after the automatic redraft) and never approved,
                or LaTeX compilation itself failed.
        """
        start = time.monotonic()
        profile_id = input.candidate_profile.id
        job_posting_id = input.job_posting.id
        if profile_id is None or job_posting_id is None:
            raise ValueError(
                "ResumeCustomizationAgent requires an already-persisted JobPosting and "
                "CandidateProfile (agents.md §6 reads job_postings/candidate_profiles) "
                "-- got one with id=None."
            )

        model = default_model_for(self.name, ctx)
        draft_template = load_prompt(_PROMPT_DOMAIN, _DRAFT_PROMPT)
        review_template = load_prompt(_PROMPT_DOMAIN, _REVIEW_PROMPT)
        candidate_profile_json = input.candidate_profile.model_dump_json()
        posting_text = input.job_posting.normalized_description
        ats_report_json = input.ats_report.model_dump_json()

        draft, review, redraft_count = self._draft_and_review(
            ctx=ctx,
            model=model,
            draft_template=draft_template,
            review_template=review_template,
            candidate_profile_json=candidate_profile_json,
            posting_text=posting_text,
            ats_report_json=ats_report_json,
        )

        if not review.approved:
            raise RenderError(
                f"Resume draft was rejected after {redraft_count} redraft(s): {review.feedback}",
                remedy="Review the feedback above; the draft/review prompts may need a fix, "
                "or the profile may lack content relevant to this posting.",
            )

        render_context = _build_render_context(input.candidate_profile, draft)
        expected_headers = _expected_headers(render_context)

        renderer_cls = get_renderer_class(_RENDERER_KIND)
        renderer = renderer_cls()
        template_source = (TEMPLATES_DIR / _TEMPLATE_RELATIVE_PATH).read_text(encoding="utf-8")
        tex_source = renderer.render(template_source, render_context)

        template = ctx.repos.documents.get_or_create_template(
            kind=_TEMPLATE_KIND, name=_TEMPLATE_NAME, file_path=_TEMPLATE_RELATIVE_PATH
        )
        output_dir = ctx.settings.data_dir / "documents" / "resumes" / str(uuid.uuid4())
        pdf_path = renderer.compile(tex_source, output_dir, base_name="resume")

        verification = verify_pdf_text(
            pdf_path,
            expected_headers=expected_headers,
            extracted_text_path=output_dir / "resume.extracted.txt",
        )

        resume_version = ResumeVersion(
            profile_id=profile_id,
            job_posting_id=job_posting_id,
            template_id=template.id or "",
            rendered_pdf_path=str(pdf_path),
            rendered_tex_path=str(output_dir / "resume.tex"),
            ats_verification_passed=verification.passed,
            ats_extracted_text_path=verification.extracted_text_path,
        )
        saved = ctx.repos.documents.save_resume_version(resume_version)

        warnings: list[str] = []
        if redraft_count:
            warnings.append(
                f"Initial draft was rejected and redrafted {redraft_count} time(s) "
                f"before approval: {review.feedback}"
            )
        if not verification.passed:
            warnings.append(
                f"PDF verification found missing section headers: {verification.missing_headers}"
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
        ats_report_json: str,
    ) -> tuple[ResumeDraft, ReviewVerdict, int]:
        reviewer_feedback = ""
        draft: ResumeDraft
        review: ReviewVerdict
        redraft_count = 0

        for attempt in range(_MAX_REDRAFTS + 1):
            draft_prompt = render_prompt(
                draft_template,
                candidate_profile_json=candidate_profile_json,
                posting_text=posting_text,
                ats_report_json=ats_report_json,
                reviewer_feedback=reviewer_feedback,
            )
            draft_response = ctx.llm.complete_structured(
                draft_prompt, model=model, response_schema=ResumeDraft, temperature=0.0
            )
            draft = draft_response.parsed

            # Independent, fresh-context call (tasks.md T11.3 checklist): its own
            # prompt reconstructed from the profile/posting/draft, never the
            # drafter's own conversation history (no such history exists at all
            # in this system's stateless single-shot LLMProvider design).
            review_prompt = render_prompt(
                review_template,
                candidate_profile_json=candidate_profile_json,
                posting_text=posting_text,
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


def _build_render_context(profile: CandidateProfile, draft: ResumeDraft) -> dict[str, object]:
    """Assemble the LaTeX template's data context.

    Name/email/phone/location/education come straight from
    ``CandidateProfile`` (never LLM-touched); summary/skills/
    experience/certifications come from the reviewed ``ResumeDraft``.
    """
    return {
        "full_name": profile.full_name or "",
        "email": profile.email,
        "phone": profile.phone,
        "location": profile.location,
        "summary": draft.summary,
        "skills": draft.skills,
        "experience": [entry.model_dump() for entry in draft.experience],
        "education": [entry.model_dump() for entry in profile.education],
        "certifications": draft.certifications,
    }


def _expected_headers(render_context: dict[str, object]) -> list[str]:
    r"""The section headers the template will actually render, given this context.

    Computed from the same data the template's own ``\BLOCK{if ...}``
    guards check, so verification never expects a header the template
    had no data to render (documents/templates/cv/resume.tex.jinja).
    """
    header_conditions = [
        ("Summary", render_context["summary"]),
        ("Skills", render_context["skills"]),
        ("Experience", render_context["experience"]),
        ("Education", render_context["education"]),
        ("Certifications", render_context["certifications"]),
    ]
    return [header for header, value in header_conditions if value]
