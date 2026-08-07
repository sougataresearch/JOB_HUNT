"""Tests for the ATS Optimization Agent (tasks.md T10.1, phases.md Phase 10).

Uses ``fake_llm_factory`` (tests/conftest.py) throughout -- no live LLM
calls. Includes dedicated tests for the deterministic keyword-gap
extraction step (agents.md §5 Tools) against known fixtures, per
tasks.md T10.1's "fixture-tested against known keyword-gap cases"
checklist item.
"""

from collections.abc import Callable
from typing import ClassVar

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from jobhunt_core.agents.ats_optimization_agent import (
    ATSOptimizationAgent,
    ATSOptimizationInput,
    _candidate_keywords,
    _flatten_profile_text,
    _missing_keywords,
)
from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
from jobhunt_core.llm.provider import LLMProvider
from jobhunt_core.schemas.ats import ATSGapClassification
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.profile import CandidateProfile, ExperienceEntry
from jobhunt_core.storage.repositories import (
    ApplicationRepo,
    ATSRepo,
    InterviewRepo,
    JobRepo,
    MatchRepo,
    ProfileRepo,
)

FakeLLMFactory = Callable[[BaseModel], LLMProvider]


class _NeverCallLLM:
    """Fails the test loudly if the agent ever calls the LLM (short-circuit paths)."""

    name: ClassVar[str] = "never"

    def complete(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("Should not call the LLM on this path")

    def complete_structured(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("Should not call the LLM on this path")


def _make_context(db_session: Session, llm: LLMProvider) -> RunContext:
    settings = Settings(
        llm=LLMConfig(default_provider="fake", providers={}),
        agents={"ats_optimization": AgentConfig(enabled=True, provider="fake", model="fake-model")},
        sources={},
    )
    repos = RepositoryBundle(
        profiles=ProfileRepo(db_session),
        jobs=JobRepo(db_session),
        matches=MatchRepo(db_session),
        ats=ATSRepo(db_session),
        applications=ApplicationRepo(db_session),
        interviews=InterviewRepo(db_session),
    )
    return RunContext(settings=settings, llm=llm, repos=repos)


# ---- Deterministic keyword-gap extraction: fixture-tested known cases ----


def test_candidate_keywords_extracts_capitalized_tech_terms() -> None:
    """Known fixture: a posting naming Python, AWS, and PostgreSQL yields those 3 keywords."""
    posting = "We need someone with Python, AWS, and PostgreSQL experience for our team."

    keywords = _candidate_keywords(posting)

    assert set(keywords) >= {"Python", "AWS", "PostgreSQL"}


def test_candidate_keywords_excludes_common_stopwords() -> None:
    """Known fixture: sentence-starting filler words are not treated as keywords."""
    posting = "We are looking for a Software Engineer. You will join our team."

    keywords = _candidate_keywords(posting)

    assert "We" not in keywords
    assert "You" not in keywords
    assert "Software" in keywords
    assert "Engineer" in keywords


def test_missing_keywords_excludes_terms_already_in_profile() -> None:
    """Known fixture: a keyword present in the profile text is not a gap."""
    posting = "Requires Python, AWS, and Kubernetes."
    profile_text = "Experienced with Python and AWS in production."

    missing = _missing_keywords(posting, profile_text)

    assert missing == ["Kubernetes"]


def test_missing_keywords_is_case_insensitive() -> None:
    """Known fixture: 'aws' in the profile still covers 'AWS' in the posting."""
    posting = "Requires AWS experience."
    profile_text = "I have used aws extensively."

    missing = _missing_keywords(posting, profile_text)

    assert missing == []


def test_flatten_profile_text_includes_experience_bullets() -> None:
    """The flattened text used for gap-checking includes experience bullets, not just skills."""
    profile = CandidateProfile(
        skills=["Python"],
        experience=[
            ExperienceEntry(
                title="Engineer", company="Acme", bullets=["Deployed services on Kubernetes"]
            )
        ],
    )

    text = _flatten_profile_text(profile)

    assert "Kubernetes" in text


# ---- Agent-level plumbing tests ----

_PROFILE = CandidateProfile(
    id="profile-1",
    full_name="Jordan Lee",
    skills=["Python", "AWS"],
    experience=[
        ExperienceEntry(
            title="Backend Engineer",
            company="Acme",
            bullets=["Built container orchestration tooling on top of Docker"],
        )
    ],
)

_POSTING = JobPosting(
    id="posting-1",
    source="greenhouse",
    source_id="1",
    title="Backend Engineer",
    url="https://example.com/jobs/1",
    normalized_description=(
        "We need a Backend Engineer with Python, AWS, and Kubernetes experience. "
        "PostgreSQL is a plus."
    ),
)

_CLASSIFICATION = ATSGapClassification(
    supported_gaps=["Kubernetes"],
    unsupported_gaps=["PostgreSQL"],
)


def test_run_produces_ats_report(db_session: Session, fake_llm_factory: FakeLLMFactory) -> None:
    """phases.md Phase 10 AC: the report distinguishes supported from unsupported gaps.

    Kubernetes is backed by the profile's "container orchestration...
    Docker" bullet (worded differently, agents.md §5) -> supported.
    PostgreSQL has no backing anywhere in the profile -> unsupported,
    never to be fabricated into a generated document.
    """
    ctx = _make_context(db_session, fake_llm_factory(_CLASSIFICATION))
    agent = ATSOptimizationAgent()

    result = agent.run(ATSOptimizationInput(candidate_profile=_PROFILE, job_posting=_POSTING), ctx)

    assert result.output.job_posting_id == "posting-1"
    assert result.output.profile_id == "profile-1"
    assert result.output.supported_gaps == ["Kubernetes"]
    assert result.output.unsupported_gaps == ["PostgreSQL"]
    assert result.model == "fake-model"
    assert result.prompt_version == "1.0"


def test_run_persists_via_repository(db_session: Session, fake_llm_factory: FakeLLMFactory) -> None:
    """The agent's output can be saved and read back through ATSRepo."""
    ctx = _make_context(db_session, fake_llm_factory(_CLASSIFICATION))
    profile = ctx.repos.profiles.save(_PROFILE.model_copy(update={"id": None}))
    posting = ctx.repos.jobs.save(_POSTING.model_copy(update={"id": None}))
    agent = ATSOptimizationAgent()

    result = agent.run(ATSOptimizationInput(candidate_profile=profile, job_posting=posting), ctx)
    saved = ctx.repos.ats.save(result.output)
    fetched = ctx.repos.ats.get(saved.id)

    assert fetched is not None
    assert fetched.supported_gaps == ["Kubernetes"]


def test_run_with_empty_posting_returns_low_confidence_report_without_llm_call(
    db_session: Session,
) -> None:
    """agents.md §5 Failure handling: empty posting text -> explicit low-confidence report."""
    ctx = _make_context(db_session, _NeverCallLLM())  # type: ignore[arg-type]
    empty_posting = _POSTING.model_copy(update={"normalized_description": "   "})
    agent = ATSOptimizationAgent()

    result = agent.run(
        ATSOptimizationInput(candidate_profile=_PROFILE, job_posting=empty_posting), ctx
    )

    assert result.output.supported_gaps == []
    assert result.output.unsupported_gaps == []
    assert any("no text to analyze" in warning for warning in result.warnings)


def test_run_with_no_keyword_gaps_skips_llm_call(db_session: Session) -> None:
    """rules.md §Performance Guidelines: no LLM call when nothing is missing."""
    ctx = _make_context(db_session, _NeverCallLLM())  # type: ignore[arg-type]
    fully_covered_posting = _POSTING.model_copy(
        update={"normalized_description": "Looking for Python and AWS experience."}
    )
    agent = ATSOptimizationAgent()

    result = agent.run(
        ATSOptimizationInput(candidate_profile=_PROFILE, job_posting=fully_covered_posting), ctx
    )

    assert result.output.supported_gaps == []
    assert result.output.unsupported_gaps == []


def test_run_raises_on_unpersisted_posting(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """Failure-path test: a posting with id=None is rejected before any LLM call."""
    ctx = _make_context(db_session, fake_llm_factory(_CLASSIFICATION))
    agent = ATSOptimizationAgent()
    unsaved_posting = _POSTING.model_copy(update={"id": None})

    with pytest.raises(ValueError, match="already-persisted"):
        input_ = ATSOptimizationInput(candidate_profile=_PROFILE, job_posting=unsaved_posting)
        agent.run(input_, ctx)


def test_prompt_sent_to_llm_contains_deterministic_gaps(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """The rendered prompt includes the deterministically-found gaps, not a re-derivation."""
    llm = fake_llm_factory(_CLASSIFICATION)
    ctx = _make_context(db_session, llm)
    agent = ATSOptimizationAgent()

    agent.run(ATSOptimizationInput(candidate_profile=_PROFILE, job_posting=_POSTING), ctx)

    assert llm.last_prompt is not None  # type: ignore[attr-defined]
    assert "Kubernetes" in llm.last_prompt  # type: ignore[attr-defined]
    assert "PostgreSQL" in llm.last_prompt  # type: ignore[attr-defined]
    # Python/AWS are already covered by the profile -- not gaps, shouldn't be listed.
    assert "- Python" not in llm.last_prompt  # type: ignore[attr-defined]
