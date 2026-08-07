"""Job Matching regression suite (testing.md §3/§4, agents.md §4 Metrics).

~10 labeled (profile, posting, expected score band) pairs, the
canonical example testing.md §4 names for preventing silent quality
drift across prompt/model changes. Same honest limitation as the
Skill Gap eval harness (Phase 6): the FakeLLMProvider is scripted with
a hand-curated "golden" response, which proves the agent's assembly
and these grading checks are correct end-to-end against realistic
fixtures -- it does not prove a *real* LLM, given the actual shipped
prompt, would score these cases within the labeled band. Swapping in a
recorded-cassette LLMProvider upgrades these same cases to a true
model-quality eval without changing this file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy.orm import Session

from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.agents.job_matching_agent import JobMatchingAgent, JobMatchingInput
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
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

CASES_DIR = Path(__file__).parent / "cases"


def _load_cases() -> list[dict[str, Any]]:
    cases = []
    for path in sorted(CASES_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            cases.append(yaml.safe_load(handle))
    return cases


_CASES = _load_cases()


def _build_posting(case_name: str, data: dict[str, Any]) -> JobPosting:
    return JobPosting(
        source="eval-fixture",
        source_id=case_name,
        url=f"https://example.com/jobs/{case_name}",
        **data,
    )


@pytest.mark.parametrize("case", _CASES, ids=[case["case_name"] for case in _CASES])
def test_job_matching_golden_case(
    case: dict[str, Any],
    db_session: Session,
    fake_llm_factory: Any,
) -> None:
    """Run the agent with a golden-scripted response and check it against expected_properties."""
    profile = CandidateProfile(**case["input"]["candidate_profile"])
    posting = _build_posting(case["case_name"], case["input"]["job_posting"])
    golden = MatchScoreExtraction(**case["golden_response"])

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
    llm = fake_llm_factory(golden)
    ctx = RunContext(settings=settings, llm=llm, repos=repos)

    saved_profile = ctx.repos.profiles.save(profile)
    saved_posting = ctx.repos.jobs.save(posting)

    agent = JobMatchingAgent()
    result = agent.run(
        JobMatchingInput(candidate_profile=saved_profile, job_posting=saved_posting), ctx
    )

    props = case["expected_properties"]
    low, high = props["score_band"]
    assert (
        low <= result.output.score <= high
    ), f"score {result.output.score} outside expected band [{low}, {high}]"
    assert result.output.rationale.strip()

    if props.get("requires_red_flag"):
        assert result.output.red_flags

    # phases.md Phase 8 AC: rationale/requirements reference concrete
    # posting/profile text, not generic filler -- checked here as "every
    # matched/missing requirement string is grounded in the posting or
    # profile text," a stronger, doable proxy for that acceptance
    # criterion (the free-text rationale itself isn't substring-checked,
    # since a faithful paraphrase is legitimate and not "generic filler").
    haystack = (
        posting.normalized_description
        + " "
        + " ".join(profile.skills)
        + " "
        + " ".join(bullet for exp in profile.experience for bullet in exp.bullets)
    ).lower()
    for requirement in result.output.matched_requirements + result.output.missing_requirements:
        assert _grounded(
            requirement, haystack
        ), f"requirement '{requirement}' not grounded in posting/profile text"


def _grounded(requirement: str, haystack: str) -> bool:
    """At least half of a requirement's significant words appear in the source text.

    Word-overlap, not an exact-substring match: real rationale text
    naturally paraphrases ("own our platform architecture" vs.
    "platform architecture ownership") without that being fabrication.
    A requirement sharing none of its words with either source text is
    what this is actually meant to catch.
    """
    words = [word.strip("+.,()") for word in requirement.lower().split()]
    significant = [word for word in words if len(word) > 2]
    if not significant:
        return True
    matches = sum(1 for word in significant if word in haystack)
    return (matches / len(significant)) >= 0.5
