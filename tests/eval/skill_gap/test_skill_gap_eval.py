"""Golden-file evaluation for the Skill Gap Agent (testing.md §3 AI Evaluation).

Each case under cases/*.yaml pairs a fixture (CandidateProfile, target
role) with a hand-curated "golden" report and structural
expected_properties. The FakeLLMProvider is scripted to return the
golden report -- this proves the agent's assembly and the
property-checks below are correct end-to-end against realistic
fixtures; it is the same honest limitation as
tests/agents/test_resume_analysis_agent.py: it cannot prove a *real*
LLM call against the actual prompt produces output this good, only
that if it did, the checks here would grade it correctly. Swapping the
FakeLLMProvider for a recorded-cassette provider once one exists
(progress_log.md Phase 5 "still open" item) upgrades these same cases
to a true model-quality eval without changing this file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy.orm import Session

from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.agents.skill_gap_agent import SkillGapAgent, SkillGapInput
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
from jobhunt_core.schemas.profile import CandidateProfile
from jobhunt_core.schemas.skill_gap import SkillGapReport
from jobhunt_core.storage.repositories import (
    ApplicationRepo,
    ATSRepo,
    DocumentRepo,
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


@pytest.mark.parametrize("case", _CASES, ids=[case["case_name"] for case in _CASES])
def test_skill_gap_golden_case(
    case: dict[str, Any],
    db_session: Session,
    fake_llm_factory: Any,
) -> None:
    """Run the agent with a golden-scripted response and check it against expected_properties."""
    profile = CandidateProfile(**case["input"]["candidate_profile"])
    target_role = case["input"].get("target_role")
    golden = SkillGapReport(**case["golden_response"])

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
        documents=DocumentRepo(db_session),
    )
    ctx = RunContext(settings=settings, llm=fake_llm_factory(golden), repos=repos)

    agent = SkillGapAgent()
    result = agent.run(SkillGapInput(candidate_profile=profile, target_role=target_role), ctx)

    props = case["expected_properties"]
    assert len(result.output.gaps) >= props["min_gaps"]
    assert len(result.output.gaps) <= props["max_gaps"]
    assert result.output.insufficient_data == props["insufficient_data"]
    gap_skills = {gap.skill for gap in result.output.gaps}
    for expected_skill in props.get("gap_skills_include", []):
        assert expected_skill in gap_skills

    # tasks.md T6.1 checklist: every gap cites profile evidence or explicit absence.
    for gap in result.output.gaps:
        assert gap.rationale.strip()
        assert gap.evidence.strip()
