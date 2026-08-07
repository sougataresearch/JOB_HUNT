"""Ranking — batch of MatchScores to a prioritized, paginated shortlist (api.md §3).

A pure function, not an agent: no LLM call, no RunContext, no I/O
(rules.md §Performance Guidelines "no agent should require an LLM call
for something a deterministic function can compute" -- ranking is
exactly that). Resolves phases.md Phase 9's "may be a mode of Job
Matching Agent... decide during implementation" note: api.md §3 had
already made this call during the doc phase (a plain ``Ranker``
Protocol, not an `Agent`), confirmed here rather than revisited, since
implementation surfaced no reason to prefer either alternative api.md
didn't already weigh.
"""

from __future__ import annotations

from datetime import UTC, datetime

from jobhunt_core.schemas.match import MatchScore, RankedPosting

_EPOCH = datetime.min.replace(tzinfo=UTC)


def rank(scores: list[MatchScore]) -> list[RankedPosting]:
    """Sort ``scores`` into a stable, prioritized ``RankedPosting`` list.

    Sort key: ``score`` descending, tie-broken by ``created_at``
    descending (most-recently-scored first). api.md §3's draft named
    ``posted_at`` (a ``JobPosting`` field) as the tie-break, but
    ``Ranker.rank()`` only receives ``list[MatchScore]`` -- joining
    against postings would require DB access, contradicting api.md
    §3's own "pure function" design intent, so ``MatchScore.created_at``
    (already on hand) is used instead. Python's ``sorted()`` is
    itself stable, so even among exact ties this always reproduces the
    same order for the same input list (phases.md Phase 9 AC).

    Args:
        scores: The batch to rank, e.g. every current ``MatchScore``
            for one candidate profile.

    Returns:
        ``RankedPosting`` entries, best match first, ``rank`` 1-indexed.
    """
    ordered = sorted(scores, key=lambda s: (-s.score, -_sort_timestamp(s)))
    return [
        RankedPosting(job_id=score.job_posting_id, score=score, rank=index + 1)
        for index, score in enumerate(ordered)
    ]


def _sort_timestamp(score: MatchScore) -> float:
    return (score.created_at or _EPOCH).timestamp()


def latest_per_posting(scores: list[MatchScore]) -> list[MatchScore]:
    """Collapse re-scoring history to the most recent score per job posting.

    ``match_scores`` retains every historical row rather than
    overwriting on re-score (database.md §6) -- ranking should reflect
    each posting's current standing, not double-count a posting that
    happens to have been scored twice.
    """
    latest_by_posting: dict[str, MatchScore] = {}
    for score in scores:
        current = latest_by_posting.get(score.job_posting_id)
        if current is None or _sort_timestamp(score) > _sort_timestamp(current):
            latest_by_posting[score.job_posting_id] = score
    return list(latest_by_posting.values())


def paginate(
    ranked: list[RankedPosting], *, page: int = 1, page_size: int = 10
) -> list[RankedPosting]:
    """Return one page of an already-ranked list (design.md §2 progressive disclosure).

    Args:
        ranked: The full ranked list (``rank()``'s output).
        page: 1-indexed page number.
        page_size: Entries per page (design.md §2's example: 10).

    Returns:
        The requested slice, possibly empty if ``page`` is past the end.

    Raises:
        ValueError: ``page`` or ``page_size`` is not a positive integer.
    """
    if page < 1 or page_size < 1:
        raise ValueError(f"page and page_size must be >= 1, got page={page}, page_size={page_size}")
    start = (page - 1) * page_size
    return ranked[start : start + page_size]
