"""Tests for orchestration.ranking (tasks.md T9.1, phases.md Phase 9 acceptance criteria)."""

from datetime import UTC, datetime, timedelta

import pytest

from jobhunt_core.orchestration.ranking import latest_per_posting, paginate, rank
from jobhunt_core.schemas.match import MatchScore

_NOW = datetime(2026, 8, 7, tzinfo=UTC)


def _score(
    job_posting_id: str,
    score: float,
    *,
    created_at: datetime | None = _NOW,
    profile_id: str = "profile-1",
) -> MatchScore:
    return MatchScore(
        job_posting_id=job_posting_id,
        profile_id=profile_id,
        score=score,
        rationale="because",
        created_at=created_at,
    )


def test_rank_sorts_by_score_descending() -> None:
    """Higher scores rank first."""
    scores = [_score("a", 50.0), _score("b", 90.0), _score("c", 70.0)]

    ranked = rank(scores)

    assert [r.job_id for r in ranked] == ["b", "c", "a"]
    assert [r.rank for r in ranked] == [1, 2, 3]


def test_rank_is_stable_for_equal_scores() -> None:
    """phases.md Phase 9 AC: same inputs -> same order, even across repeated calls."""
    scores = [_score("a", 80.0), _score("b", 80.0), _score("c", 80.0)]

    first = rank(scores)
    second = rank(list(scores))  # a fresh list with the same elements in the same order

    assert [r.job_id for r in first] == [r.job_id for r in second] == ["a", "b", "c"]


def test_rank_tie_breaks_by_created_at_descending() -> None:
    """Among equal scores, the most-recently-scored posting ranks first."""
    older = _score("old", 80.0, created_at=_NOW - timedelta(days=1))
    newer = _score("new", 80.0, created_at=_NOW)

    ranked = rank([older, newer])

    assert [r.job_id for r in ranked] == ["new", "old"]


def test_rank_treats_missing_created_at_as_oldest() -> None:
    """A score with no created_at never outranks a tied score that has one."""
    unknown = _score("unknown", 80.0, created_at=None)
    known = _score("known", 80.0, created_at=_NOW)

    ranked = rank([unknown, known])

    assert [r.job_id for r in ranked] == ["known", "unknown"]


def test_rank_empty_list_returns_empty_list() -> None:
    """No scores -> no ranked postings, not an error."""
    assert rank([]) == []


def test_latest_per_posting_keeps_only_the_most_recent_score() -> None:
    """Re-scoring history (database.md §6) is collapsed to one entry per posting."""
    old_score = _score("posting-1", 40.0, created_at=_NOW - timedelta(days=5))
    new_score = _score("posting-1", 85.0, created_at=_NOW)
    other_posting = _score("posting-2", 60.0, created_at=_NOW)

    latest = latest_per_posting([old_score, new_score, other_posting])

    by_posting = {s.job_posting_id: s for s in latest}
    assert len(latest) == 2
    assert by_posting["posting-1"].score == 85.0
    assert by_posting["posting-2"].score == 60.0


def test_paginate_returns_correct_slice() -> None:
    """Page 2 with page_size=2 returns entries 3-4."""
    scores = [_score(f"p{i}", float(100 - i)) for i in range(5)]
    ranked = rank(scores)

    page = paginate(ranked, page=2, page_size=2)

    assert [r.job_id for r in page] == ["p2", "p3"]


def test_paginate_past_the_end_returns_empty() -> None:
    """A page number beyond the data returns an empty list, not an error."""
    ranked = rank([_score("a", 50.0)])

    page = paginate(ranked, page=5, page_size=10)

    assert page == []


def test_paginate_default_page_size_is_ten() -> None:
    """design.md §2's example: default page size shows the top 10."""
    scores = [_score(f"p{i}", float(100 - i)) for i in range(15)]
    ranked = rank(scores)

    page = paginate(ranked)

    assert len(page) == 10
    assert page[0].job_id == "p0"


@pytest.mark.parametrize("page,page_size", [(0, 10), (1, 0), (-1, 10)])
def test_paginate_rejects_non_positive_page_or_size(page: int, page_size: int) -> None:
    """page and page_size must both be >= 1."""
    with pytest.raises(ValueError, match="must be >= 1"):
        paginate([], page=page, page_size=page_size)
