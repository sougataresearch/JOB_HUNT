"""Tests for the Job Matching Agent (tasks.md T8.1, phases.md Phase 8).

Uses ``fake_llm_factory`` (tests/conftest.py) throughout -- no live LLM
calls. These are the plumbing tests required by rules.md's Testing
Requirements; the ~10-case regression suite lives separately under
tests/eval/job_matching/ (testing.md §3/§4).
"""

from collections.abc import Callable
from typing import ClassVar

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.agents.job_matching_agent import JobMatchingAgent, JobMatchingInput
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
from jobhunt_core.llm.provider import LLMProvider
from jobhunt_core.llm.types import StructuredLLMResponse
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.match import MatchScoreExtraction
from jobhunt_core.schemas.profile import CandidateProfile
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
    id="profile-1",
    full_name="Jordan Lee",
    skills=["Python", "Go", "PostgreSQL"],
)

_POSTING = JobPosting(
    id="posting-1",
    source="greenhouse",
    source_id="1",
    title="Backend Engineer",
    url="https://example.com/jobs/1",
    normalized_description="We need a Python backend engineer with PostgreSQL experience.",
)

_EXTRACTION = MatchScoreExtraction(
    score=82.0,
    matched_requirements=["Python", "PostgreSQL"],
    missing_requirements=["Kubernetes"],
    red_flags=[],
    rationale="Candidate lists Python and PostgreSQL, matching the posting's core stack.",
)


def _make_context(db_session: Session, llm: LLMProvider) -> RunContext:
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
    )
    return RunContext(settings=settings, llm=llm, repos=repos)


def test_run_produces_match_score(db_session: Session, fake_llm_factory: FakeLLMFactory) -> None:
    """Given a scripted extraction, run() assembles a full MatchScore."""
    ctx = _make_context(db_session, fake_llm_factory(_EXTRACTION))
    agent = JobMatchingAgent()

    result = agent.run(JobMatchingInput(candidate_profile=_PROFILE, job_posting=_POSTING), ctx)

    assert result.output.score == 82.0
    assert result.output.job_posting_id == "posting-1"
    assert result.output.profile_id == "profile-1"
    assert result.output.matched_requirements == ["Python", "PostgreSQL"]
    assert result.output.rationale
    assert result.model == "fake-model"
    assert result.prompt_version == "1.0"


def test_run_persists_via_repository(db_session: Session, fake_llm_factory: FakeLLMFactory) -> None:
    """The agent's output can be saved and read back through MatchRepo.

    match_scores.job_posting_id/profile_id are real FKs, so this needs
    rows that actually exist -- saved via the repos first, unlike the
    other tests here which use hardcoded ids that never touch the DB.
    """
    ctx = _make_context(db_session, fake_llm_factory(_EXTRACTION))
    profile = ctx.repos.profiles.save(_PROFILE.model_copy(update={"id": None}))
    posting = ctx.repos.jobs.save(_POSTING.model_copy(update={"id": None}))
    agent = JobMatchingAgent()

    result = agent.run(JobMatchingInput(candidate_profile=profile, job_posting=posting), ctx)
    saved = ctx.repos.matches.save(result.output)
    fetched = ctx.repos.matches.get(saved.id)

    assert fetched is not None
    assert fetched.score == 82.0


def test_rationale_is_never_empty(db_session: Session) -> None:
    """Schema-validation test: MatchScoreExtraction cannot be built without a rationale."""
    with pytest.raises(ValidationError):
        MatchScoreExtraction(score=50.0)  # type: ignore[call-arg]


def test_run_raises_on_unpersisted_posting(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """Failure-path test: a posting with id=None is rejected before any LLM call."""
    ctx = _make_context(db_session, fake_llm_factory(_EXTRACTION))
    agent = JobMatchingAgent()
    unsaved_posting = _POSTING.model_copy(update={"id": None})

    with pytest.raises(ValueError, match="already-persisted"):
        agent.run(JobMatchingInput(candidate_profile=_PROFILE, job_posting=unsaved_posting), ctx)


def test_run_uses_temperature_zero(db_session: Session, fake_llm_factory: FakeLLMFactory) -> None:
    """PRD.md §6 Determinism: the agent always requests temperature=0."""
    llm = fake_llm_factory(_EXTRACTION)
    ctx = _make_context(db_session, llm)
    agent = JobMatchingAgent()

    agent.run(JobMatchingInput(candidate_profile=_PROFILE, job_posting=_POSTING), ctx)

    assert llm.last_temperature == 0.0  # type: ignore[attr-defined]


def test_same_scripted_response_is_reproducible(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """Given a fixed model response, repeated runs produce an identical score/rationale."""
    ctx1 = _make_context(db_session, fake_llm_factory(_EXTRACTION))
    ctx2 = _make_context(db_session, fake_llm_factory(_EXTRACTION))
    agent = JobMatchingAgent()

    result1 = agent.run(JobMatchingInput(candidate_profile=_PROFILE, job_posting=_POSTING), ctx1)
    result2 = agent.run(JobMatchingInput(candidate_profile=_PROFILE, job_posting=_POSTING), ctx2)

    assert result1.output.score == result2.output.score
    assert result1.output.rationale == result2.output.rationale
    assert result1.output.matched_requirements == result2.output.matched_requirements


class _ValidatesOnceThenFailsLLM:
    """Raises ValidationError on the first complete_structured() call, succeeds on the second."""

    name: ClassVar[str] = "flaky"

    def __init__(self, good_response: BaseModel, *, always_fail: bool = False) -> None:
        self._good_response = good_response
        self._always_fail = always_fail
        self.calls = 0

    def complete(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("not used by JobMatchingAgent")

    def complete_structured(self, prompt, *, model, response_schema, temperature=0.0):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self._always_fail or self.calls == 1:
            response_schema.model_validate({})  # missing required fields -> real ValidationError
        return StructuredLLMResponse(
            text="fake",
            parsed=response_schema.model_validate(self._good_response.model_dump()),
            tokens_in=1,
            tokens_out=1,
            cost_estimate_usd=0.0,
            latency_ms=1,
        )


def test_schema_validation_failure_is_retried_once_then_succeeds(db_session: Session) -> None:
    """agents.md §4: a schema-invalid first response gets one stricter re-ask."""
    llm = _ValidatesOnceThenFailsLLM(_EXTRACTION)
    ctx = _make_context(db_session, llm)  # type: ignore[arg-type]
    agent = JobMatchingAgent()

    result = agent.run(JobMatchingInput(candidate_profile=_PROFILE, job_posting=_POSTING), ctx)

    assert result.output.score == 82.0
    assert llm.calls == 2


def test_schema_validation_failure_twice_propagates(db_session: Session) -> None:
    """Never silently returns a partially-parsed score -- a second failure raises."""
    llm = _ValidatesOnceThenFailsLLM(_EXTRACTION, always_fail=True)
    ctx = _make_context(db_session, llm)  # type: ignore[arg-type]
    agent = JobMatchingAgent()

    with pytest.raises(ValidationError):
        agent.run(JobMatchingInput(candidate_profile=_PROFILE, job_posting=_POSTING), ctx)

    assert llm.calls == 2


def test_prompt_sent_to_llm_contains_profile_and_posting_text(
    db_session: Session, fake_llm_factory: FakeLLMFactory
) -> None:
    """The rendered prompt includes both the profile JSON and the posting's text."""
    llm = fake_llm_factory(_EXTRACTION)
    ctx = _make_context(db_session, llm)
    agent = JobMatchingAgent()

    agent.run(JobMatchingInput(candidate_profile=_PROFILE, job_posting=_POSTING), ctx)

    assert llm.last_prompt is not None  # type: ignore[attr-defined]
    assert "Jordan Lee" in llm.last_prompt  # type: ignore[attr-defined]
    assert "PostgreSQL experience" in llm.last_prompt  # type: ignore[attr-defined]
