"""Tests for the Skill Gap Agent (tasks.md T6.1, phases.md Phase 6).

Uses the ``fake_llm_factory`` fixture (tests/conftest.py) throughout --
no live LLM calls. These are the plumbing tests required by rules.md's
Testing Requirements ((a) schema-validation, (b) golden-file prompt
test, (c) failure-path); the golden-file eval cases live separately
under tests/eval/skill_gap/ (testing.md §3 AI Evaluation) since they
exercise fixture-driven cases rather than inline-scripted ones.
"""

from collections.abc import Callable

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.agents.skill_gap_agent import SkillGapAgent, SkillGapInput
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
from jobhunt_core.errors import LLMProviderError
from jobhunt_core.llm.provider import LLMProvider
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.profile import CandidateProfile
from jobhunt_core.schemas.skill_gap import SkillGap, SkillGapPriority, SkillGapReport
from jobhunt_core.storage.repositories import (
    ApplicationRepo,
    ATSRepo,
    InterviewRepo,
    JobRepo,
    MatchRepo,
    ProfileRepo,
)

FakeLLMFactory = Callable[[BaseModel], LLMProvider]

_PROFILE = CandidateProfile(
    full_name="Jordan Lee",
    skills=["Python", "Go", "PostgreSQL", "Kubernetes", "AWS"],
)

_REPORT = SkillGapReport(
    gaps=[
        SkillGap(
            skill="Machine learning frameworks (PyTorch/TensorFlow)",
            priority=SkillGapPriority.HIGH,
            rationale="Target role requires production ML systems experience.",
            evidence="Not present in skills (Python, Go, PostgreSQL, Kubernetes, AWS).",
        )
    ],
    summary="Strong backend/infra foundation; missing ML tooling for this role.",
    insufficient_data=False,
)


def _make_context(db_session: Session, llm: LLMProvider) -> RunContext:
    settings = Settings(
        llm=LLMConfig(default_provider="fake", providers={}),
        agents={"skill_gap": AgentConfig(enabled=True, provider="fake", model="fake-model")},
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


def test_run_produces_skill_gap_report(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """Given a scripted report, run() returns it wrapped in an AgentResult."""
    ctx = _make_context(db_session, fake_llm_factory(_REPORT))
    agent = SkillGapAgent()
    result = agent.run(SkillGapInput(candidate_profile=_PROFILE, target_role="ML Engineer"), ctx)

    assert result.output.gaps[0].skill == "Machine learning frameworks (PyTorch/TensorFlow)"
    assert result.model == "fake-model"
    assert result.prompt_version == "1.0"


def test_every_gap_has_rationale_and_evidence(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """Schema-validation test: SkillGap cannot be built without rationale/evidence."""
    with pytest.raises(ValidationError):
        SkillGap(skill="x", priority=SkillGapPriority.LOW)  # type: ignore[call-arg]


def test_input_requires_target_role_or_postings() -> None:
    """Failure-path test: neither target_role nor postings raises ValidationError."""
    with pytest.raises(ValidationError):
        SkillGapInput(candidate_profile=_PROFILE)


def test_input_accepts_postings_without_target_role() -> None:
    """A list of postings alone satisfies the target requirement."""
    posting = JobPosting(
        source="manual",
        source_id="abc123",
        title="ML Engineer",
        url="https://example.com/job/abc123",
        normalized_description="Build production ML systems using PyTorch.",
    )
    skill_gap_input = SkillGapInput(candidate_profile=_PROFILE, postings=[posting])
    assert skill_gap_input.postings == [posting]


def test_run_propagates_llm_provider_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failure-path test: an LLM provider failure surfaces, not swallowed."""

    class _FailingLLM:
        name = "failing"

        def complete(self, *args: object, **kwargs: object) -> object:
            raise LLMProviderError("boom")

        def complete_structured(self, *args: object, **kwargs: object) -> object:
            raise LLMProviderError("boom")

    ctx = _make_context(db_session, _FailingLLM())  # type: ignore[arg-type]
    agent = SkillGapAgent()

    with pytest.raises(LLMProviderError):
        agent.run(SkillGapInput(candidate_profile=_PROFILE, target_role="ML Engineer"), ctx)


def test_prompt_sent_to_llm_contains_profile_and_target(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """The rendered prompt includes both the profile JSON and the target role text."""
    llm = fake_llm_factory(_REPORT)
    ctx = _make_context(db_session, llm)
    agent = SkillGapAgent()

    agent.run(SkillGapInput(candidate_profile=_PROFILE, target_role="ML Engineer role"), ctx)

    assert llm.last_prompt is not None  # type: ignore[attr-defined]
    assert "Jordan Lee" in llm.last_prompt  # type: ignore[attr-defined]
    assert "ML Engineer role" in llm.last_prompt  # type: ignore[attr-defined]


def test_target_context_uses_postings_when_no_target_role(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """With postings but no target_role, the prompt is built from posting text."""
    posting = JobPosting(
        source="manual",
        source_id="abc123",
        title="Senior ML Engineer",
        url="https://example.com/job/abc123",
        normalized_description="Own our PyTorch-based recommendation pipeline.",
    )
    llm = fake_llm_factory(_REPORT)
    ctx = _make_context(db_session, llm)
    agent = SkillGapAgent()

    agent.run(SkillGapInput(candidate_profile=_PROFILE, postings=[posting]), ctx)

    assert "Senior ML Engineer" in llm.last_prompt  # type: ignore[attr-defined]
    assert "recommendation pipeline" in llm.last_prompt  # type: ignore[attr-defined]
