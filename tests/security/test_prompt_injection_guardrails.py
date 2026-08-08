"""Prompt-injection guardrail tests (testing.md §9, rules.md §Prompt Engineering Standards).

Every prompt that ingests untrusted content (job posting text, scraped
content, a user-uploaded CV) must (a) wrap it in ``<untrusted_content>``
delimiters and (b) explicitly instruct the model to ignore embedded
instructions within it (prompts.md's own "mandatory block", design.md
§12). This is a structural check across the whole prompt library, not
one agent's test -- doesn't mirror a single ``src/jobhunt_core`` module
1:1, same exception already applying to ``tests/e2e/``.

Honest limitation, same as every eval suite in this project: this
proves the *prompt structure* is defensive (delimited, instructed to
ignore embedded commands) and that the *agent's own code* doesn't do
anything special when injection-shaped text is present. It cannot
prove a real LLM actually resists the injection -- that needs a live
or recorded-cassette call (rules.md forbids live calls in unit tests;
the recorded-cassette upgrade path is a carried-forward open item).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.agents.job_matching_agent import JobMatchingAgent, JobMatchingInput
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
from jobhunt_core.llm.types import StructuredLLMResponse
from jobhunt_core.prompts.loader import load_prompt, render_prompt
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.match import MatchScore, MatchScoreExtraction
from jobhunt_core.schemas.profile import CandidateProfile
from jobhunt_core.storage.repositories import (
    ApplicationRepo,
    ATSRepo,
    DocumentRepo,
    InterviewRepo,
    JobRepo,
    MatchRepo,
    ProfileRepo,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "postings"

# (agent_domain, prompt_name, render_kwargs) for every prompt in the
# library that accepts untrusted posting/CV content -- prompts.md's own
# guardrail block is "mandatory in every prompt that ingests job-posting
# text or any other externally-sourced content." "{injected}" marks
# where the injection-attempt fixture text is substituted in.
_UNTRUSTED_CONTENT_PROMPTS: list[tuple[str, str, dict[str, Any]]] = [
    ("job_matching", "score", {"candidate_profile_json": "{}", "posting_text": "{injected}"}),
    (
        "ats",
        "analyze",
        {"candidate_profile_json": "{}", "posting_text": "{injected}", "raw_keyword_gaps": ""},
    ),
    ("skill_gap", "analyze", {"candidate_profile_json": "{}", "target_context": "{injected}"}),
    (
        "resume_customization",
        "draft",
        {
            "candidate_profile_json": "{}",
            "posting_text": "{injected}",
            "ats_report_json": "{}",
            "reviewer_feedback": "",
        },
    ),
    (
        "resume_customization",
        "review",
        {"candidate_profile_json": "{}", "posting_text": "{injected}", "draft_content": "{}"},
    ),
    (
        "cover_letter",
        "draft",
        {
            "candidate_profile_json": "{}",
            "posting_text": "{injected}",
            "resume_text": "",
            "reviewer_feedback": "",
        },
    ),
    (
        "cover_letter",
        "review",
        {
            "candidate_profile_json": "{}",
            "posting_text": "{injected}",
            "resume_text": "",
            "draft_content": "{}",
        },
    ),
    ("email", "draft", {"job_title": "Engineer", "posting_text": "{injected}"}),
    (
        "interview",
        "prepare",
        {
            "posting_text": "{injected}",
            "resume_text": "",
            "match_score_json": "{}",
            "interview_type": "phone_screen",
            "grounding_note": "",
        },
    ),
    ("resume_analysis", "extract_profile", {"cv_raw_text": "{injected}"}),
]


@pytest.fixture
def injection_text() -> str:
    return (FIXTURES_DIR / "injection_attempt.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "agent_domain,prompt_name,kwargs",
    _UNTRUSTED_CONTENT_PROMPTS,
    ids=[f"{domain}/{name}" for domain, name, _ in _UNTRUSTED_CONTENT_PROMPTS],
)
def test_prompt_wraps_untrusted_content_with_guardrail(
    agent_domain: str, prompt_name: str, kwargs: dict[str, Any], injection_text: str
) -> None:
    """Every prompt handling untrusted content delimits it and instructs the model to ignore it."""
    template = load_prompt(agent_domain, prompt_name)

    system_text = template.system.lower()
    assert "ignore" in system_text and "instruction" in system_text, (
        f"{agent_domain}/{prompt_name} System section has no explicit "
        "ignore-embedded-instructions guardrail (prompts.md mandatory block)"
    )

    resolved_kwargs = {
        key: (injection_text if value == "{injected}" else value) for key, value in kwargs.items()
    }
    rendered = render_prompt(template, **resolved_kwargs)

    assert "<untrusted_content>" in rendered and "</untrusted_content>" in rendered
    start = rendered.index("<untrusted_content>")
    end = rendered.index("</untrusted_content>")
    assert injection_text in rendered[start:end], (
        f"{agent_domain}/{prompt_name} does not place the untrusted content "
        "inside its <untrusted_content> delimiters"
    )


def test_job_matching_agent_ignores_embedded_score_override(
    db_session: Any, injection_text: str
) -> None:
    """An injection-shaped posting flows through as inert data, never as a code-level effect.

    The FakeLLMProvider here is scripted to return a normal,
    unremarkable score -- proving JobMatchingAgent's own code applies
    no special handling to injection-shaped text (it doesn't parse the
    posting for embedded "instructions" and act on them; the text is
    just interpolated into the delimited block like any other posting).
    This does NOT prove a real LLM would resist the injection -- see
    this module's docstring.
    """

    class _FakeLLM:
        name = "fake"

        def complete(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("unused")

        def complete_structured(
            self, prompt: str, *, model: str, response_schema: type, temperature: float = 0.0
        ) -> StructuredLLMResponse[MatchScoreExtraction]:
            assert injection_text in prompt
            parsed = MatchScoreExtraction(
                score=55.0,
                matched_requirements=["Python"],
                missing_requirements=["5+ years experience"],
                rationale="Partial overlap on Python; seniority unclear from the posting text.",
            )
            return StructuredLLMResponse(
                text="fake",
                parsed=parsed,
                tokens_in=1,
                tokens_out=1,
                cost_estimate_usd=0.0,
                latency_ms=1,
            )

    settings = Settings(
        llm=LLMConfig(default_provider="fake", providers={}),
        agents={"job_matching": AgentConfig(enabled=True, provider="fake", model="fake-model")},
        sources={},
    )
    repos = RepositoryBundle(
        profiles=ProfileRepo(db_session),
        jobs=JobRepo(db_session),
        matches=MatchRepo(db_session),
        ats=ATSRepo(db_session),
        applications=ApplicationRepo(db_session),
        interviews=InterviewRepo(db_session),
        documents=DocumentRepo(db_session),
    )
    ctx = RunContext(settings=settings, llm=_FakeLLM(), repos=repos)  # type: ignore[arg-type]

    profile = ctx.repos.profiles.save(CandidateProfile(full_name="Jane Doe", skills=["Python"]))
    posting = ctx.repos.jobs.save(
        JobPosting(
            source="greenhouse",
            source_id="1",
            title="Senior Backend Engineer",
            url="https://example.com/1",
            normalized_description=injection_text,
        )
    )

    result = JobMatchingAgent().run(
        JobMatchingInput(candidate_profile=profile, job_posting=posting), ctx
    )

    match_score: MatchScore = result.output
    assert match_score.score == 55.0
    assert match_score.score != 100
    assert "everything" not in match_score.matched_requirements
