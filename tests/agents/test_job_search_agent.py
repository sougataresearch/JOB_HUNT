"""Tests for the Job Search Agent (tasks.md T7.4, phases.md Phase 7 acceptance criteria).

No live network/LLM calls -- fake ``JobSource`` implementations stand
in for real connectors, and no LLM is used at all (agents.md §3: this
agent is deterministic, no prompt template).
"""

from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.orm import Session

from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.agents.job_search_agent import JobSearchAgent
from jobhunt_core.config.settings import LLMConfig, Settings
from jobhunt_core.errors import SourceFetchError
from jobhunt_core.schemas.job import RawPosting, SearchQuery
from jobhunt_core.storage.repositories import (
    ApplicationRepo,
    ATSRepo,
    DocumentRepo,
    InterviewRepo,
    JobRepo,
    MatchRepo,
    ProfileRepo,
)


class _FakeLLM:
    """Unused by JobSearchAgent, but RunContext requires an llm -- never called."""

    name: ClassVar[str] = "fake"

    def complete(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("JobSearchAgent should never call the LLM")

    def complete_structured(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("JobSearchAgent should never call the LLM")


class _FixedSource:
    """Returns a fixed, caller-supplied list of RawPostings every call."""

    def __init__(self, name: str, postings: list[RawPosting]) -> None:
        self.name = name
        self._postings = postings
        self.call_count = 0

    def search(self, query: SearchQuery, ctx: RunContext) -> list[RawPosting]:
        self.call_count += 1
        return list(self._postings)


class _AlwaysFailingSource:
    """Always raises SourceFetchError -- simulates a fully down source."""

    name: ClassVar[str] = "always_failing"

    def search(self, query: SearchQuery, ctx: RunContext) -> list[RawPosting]:
        raise SourceFetchError("simulated total outage")


def _raw_posting(
    source: str = "greenhouse",
    source_id: str = "1",
    title: str = "Backend Engineer",
    company: str = "Acme",
    location: str = "Remote",
    content: str = "Build things.",
) -> RawPosting:
    return RawPosting(
        source=source,
        source_id=source_id,
        title=title,
        company=company,
        location=location,
        url=f"https://example.com/{source}/{source_id}",
        raw_content=content,
        fetched_at=datetime.now(UTC),
    )


def _make_context(db_session: Session, sources: dict[str, object]) -> RunContext:
    settings = Settings(
        llm=LLMConfig(default_provider="fake", providers={}),
        agents={},
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
    return RunContext(settings=settings, llm=_FakeLLM(), repos=repos, sources=sources)  # type: ignore[arg-type]


def test_run_persists_and_returns_new_postings(db_session: Session) -> None:
    """A fresh posting from an enabled source is normalized, saved, and returned."""
    source = _FixedSource("greenhouse", [_raw_posting()])
    ctx = _make_context(db_session, {"greenhouse": source})
    agent = JobSearchAgent()

    result = agent.run(SearchQuery(), ctx)

    assert len(result.output.postings) == 1
    posting = result.output.postings[0]
    assert posting.id is not None
    assert posting.title == "Backend Engineer"
    assert posting.remote_type.value == "remote"
    assert posting.search_run_id == result.output.search_run_id


def test_rerun_with_overlapping_results_produces_no_duplicate_rows(db_session: Session) -> None:
    """Phase 7 acceptance criteria: running search twice with overlapping results dedupes."""
    source = _FixedSource("greenhouse", [_raw_posting(source_id="1"), _raw_posting(source_id="2")])
    ctx = _make_context(db_session, {"greenhouse": source})
    agent = JobSearchAgent()

    first = agent.run(SearchQuery(), ctx)
    second = agent.run(SearchQuery(), ctx)

    assert len(first.output.postings) == 2
    assert len(second.output.postings) == 0  # both already seen -- nothing new
    all_postings = ctx.repos.jobs.list()
    assert len(all_postings) == 2  # no duplicate rows despite two runs


def test_rerun_with_one_new_posting_only_inserts_the_new_one(db_session: Session) -> None:
    """A partially-overlapping re-run inserts only the genuinely new posting."""
    source = _FixedSource("greenhouse", [_raw_posting(source_id="1")])
    ctx = _make_context(db_session, {"greenhouse": source})
    agent = JobSearchAgent()
    agent.run(SearchQuery(), ctx)

    source._postings.append(_raw_posting(source_id="2"))
    second = agent.run(SearchQuery(), ctx)

    assert len(second.output.postings) == 1
    assert second.output.postings[0].source_id == "2"
    assert len(ctx.repos.jobs.list()) == 2


def test_failing_source_does_not_abort_the_batch(db_session: Session) -> None:
    """design.md §10 per-item isolation: one failing source doesn't block the others."""
    good_source = _FixedSource("greenhouse", [_raw_posting()])
    bad_source = _AlwaysFailingSource()
    ctx = _make_context(db_session, {"greenhouse": good_source, "always_failing": bad_source})
    agent = JobSearchAgent()

    result = agent.run(SearchQuery(), ctx)

    assert len(result.output.postings) == 1  # the good source's posting still made it through
    assert any("always_failing" in warning for warning in result.warnings)


def test_fuzzy_duplicate_across_sources_is_flagged_not_merged(db_session: Session) -> None:
    """database.md §5: cross-source near-duplicates are flagged, kept as separate rows."""
    same_shape = {
        "title": "Backend Engineer",
        "company": "Acme",
        "location": "Remote",
        "content": "Identical description text.",
    }
    posting_a = _raw_posting(source="greenhouse", source_id="1", **same_shape)
    posting_b = _raw_posting(source="manual_import", source_id="x", **same_shape)
    source_a = _FixedSource("greenhouse", [posting_a])
    source_b = _FixedSource("manual_import", [posting_b])
    ctx = _make_context(db_session, {"greenhouse": source_a, "manual_import": source_b})
    agent = JobSearchAgent()

    result = agent.run(SearchQuery(), ctx)

    assert len(result.output.postings) == 2  # both kept, not merged
    assert any("likely duplicate" in warning for warning in result.warnings)


def test_search_run_is_recorded_with_correct_counts(db_session: Session) -> None:
    """A SearchRun row is created and completed with accurate found/new counts."""
    source = _FixedSource("greenhouse", [_raw_posting(source_id="1"), _raw_posting(source_id="2")])
    ctx = _make_context(db_session, {"greenhouse": source})
    agent = JobSearchAgent()

    result = agent.run(SearchQuery(keywords=["python"]), ctx)

    assert result.output.search_run_id is not None
    search_run = ctx.repos.jobs.get_search_run(result.output.search_run_id)
    assert search_run is not None
    assert search_run.postings_found == 2
    assert search_run.postings_deduped_new == 2
    assert search_run.completed_at is not None
    assert search_run.sources_queried == ["greenhouse"]


def test_no_enabled_sources_returns_empty_result(db_session: Session) -> None:
    """An empty ctx.sources (nothing enabled) is a safe no-op, not an error."""
    ctx = _make_context(db_session, {})
    agent = JobSearchAgent()

    result = agent.run(SearchQuery(), ctx)

    assert result.output.postings == []
    assert result.warnings == []
