"""Golden-file evaluation for the Interview Prep Agent (testing.md §3 AI Evaluation).

Each case under cases/*.yaml pairs a fixture (job posting, resume
text, match score, interview type) with a hand-curated "golden"
response and structural expected_properties. The FakeLLMProvider is
scripted to return the golden response -- same honest limitation as
every other eval suite in this project (tests/eval/skill_gap,
tests/eval/job_matching): this proves the agent's assembly and the
grading checks below are correct end-to-end, not that a *real* LLM
call against the shipped prompt would produce output this good.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy.orm import Session

from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.agents.interview_prep_agent import InterviewPrepAgent, InterviewPrepInput
from jobhunt_core.config.settings import AgentConfig, LLMConfig, Settings
from jobhunt_core.schemas.application import Application
from jobhunt_core.schemas.document import ResumeVersion
from jobhunt_core.schemas.interview import InterviewPrepExtraction, InterviewType
from jobhunt_core.schemas.job import JobPosting
from jobhunt_core.schemas.match import MatchScore
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

CASES_DIR = Path(__file__).parent / "cases"


def _load_cases() -> list[dict[str, Any]]:
    cases = []
    for path in sorted(CASES_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            cases.append(yaml.safe_load(handle))
    return cases


_CASES = _load_cases()


@pytest.mark.parametrize("case", _CASES, ids=[case["case_name"] for case in _CASES])
def test_interview_prep_golden_case(
    case: dict[str, Any],
    db_session: Session,
    tmp_path: Path,
    fake_llm_factory: Any,
) -> None:
    """Run the agent with a golden-scripted response and check it against expected_properties."""
    golden = InterviewPrepExtraction(**case["golden_response"])
    settings = Settings(
        llm=LLMConfig(default_provider="fake", providers={}),
        agents={"interview_prep": AgentConfig(enabled=True, provider="fake", model="fake-model")},
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

    posting = ctx.repos.jobs.save(
        JobPosting(
            source="eval-fixture",
            source_id=case["case_name"],
            url=f"https://example.com/jobs/{case['case_name']}",
            **case["input"]["job_posting"],
        )
    )
    profile = ctx.repos.profiles.save(CandidateProfile(full_name="Jane Doe"))
    template = ctx.repos.documents.get_or_create_template(
        kind="resume", name="resume", file_path="cv/resume.tex.jinja"
    )
    resume_text_path = tmp_path / f"{case['case_name']}.resume.extracted.txt"
    resume_text_path.write_text(case["input"]["resume_text"], encoding="utf-8")
    resume_version = ctx.repos.documents.save_resume_version(
        ResumeVersion(
            profile_id=profile.id,
            job_posting_id=posting.id,
            template_id=template.id or "",
            rendered_pdf_path="r.pdf",
            rendered_tex_path="r.tex",
            ats_verification_passed=True,
            ats_extracted_text_path=str(resume_text_path),
        )
    )
    match_score = ctx.repos.matches.save(
        MatchScore(job_posting_id=posting.id, profile_id=profile.id, **case["input"]["match_score"])
    )
    application = ctx.repos.applications.create(
        Application(job_posting_id=posting.id, resume_version_id=resume_version.id)
    )

    agent = InterviewPrepAgent()
    result = agent.run(
        InterviewPrepInput(
            application=application,
            job_posting=posting,
            resume_version=resume_version,
            match_score=match_score,
            interview_type=InterviewType(case["input"]["interview_type"]),
        ),
        ctx,
    )

    props = case["expected_properties"]
    assert len(result.output.questions) >= props["min_questions"]
    categories = {question.category.value for question in result.output.questions}
    for expected_category in props.get("categories_include", []):
        assert expected_category in categories
    assert bool(result.warnings) == props["low_grounding"]

    # phases.md Phase 15 AC / agents.md §10 Metrics: talking points
    # traceable to specific resume bullets or posting lines, not
    # generic interview advice.
    haystack = (
        case["input"]["resume_text"] + " " + case["input"]["job_posting"]["normalized_description"]
    ).lower()
    for question in result.output.questions:
        for point in question.suggested_talking_points:
            assert _grounded(
                point, haystack
            ), f"talking point '{point}' not grounded in resume/posting text"


def _grounded(point: str, haystack: str) -> bool:
    """At least half of a talking point's significant words appear in the source text.

    Word-overlap, not exact-substring match -- same rationale as
    tests/eval/job_matching/test_job_matching_eval.py's ``_grounded()``:
    real talking points naturally paraphrase without that being
    fabrication; a point sharing none of its words with either source
    is what this actually catches.
    """
    words = [word.strip("+.,()") for word in point.lower().split()]
    significant = [word for word in words if len(word) > 2]
    if not significant:
        return True
    matches = sum(1 for word in significant if word in haystack)
    return (matches / len(significant)) >= 0.5
