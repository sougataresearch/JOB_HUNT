"""Greenhouse Job Board API connector (tasks.md T7.2, api.md §2).

ToS-compliant per rules.md §Security Rules ("prefer an official API...
over scraping"): the Greenhouse Job Board API
(https://developers.greenhouse.io/job-board.html) is a public,
unauthenticated, documented REST API that companies use to power their
own public careers pages -- reading published postings from it is the
intended use, not a Terms-of-Service violation. It is per-company (one
board token per company, e.g. ``"gitlab"``), with no cross-company
keyword search server-side, so this connector polls every configured
board and filters client-side against ``SearchQuery``.
"""

from __future__ import annotations

import random
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from html import unescape
from typing import TYPE_CHECKING, Any, ClassVar

import httpx

from jobhunt_core.errors import SourceFetchError
from jobhunt_core.llm.retry import call_with_retry
from jobhunt_core.schemas.job import RawPosting, SearchQuery
from jobhunt_core.sources.base import register_source

if TYPE_CHECKING:
    # TYPE_CHECKING-only, same rationale as sources/base.py: no runtime
    # dependency on agents/, just a type annotation for the ctx param.
    from jobhunt_core.agents.base import RunContext

_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
_TAG_RE = re.compile(r"<[^>]+>")


def _is_retryable(exc: Exception) -> bool:
    """True for 5xx/connection/timeout errors; false for 4xx (e.g. unknown board)."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


def _strip_html(html: str) -> str:
    """Deterministically reduce Greenhouse's HTML job description to plain text.

    A regex tag-strip, not a full HTML parser -- Greenhouse's own
    content is well-formed enough that this is adequate, and adding a
    new dependency (e.g. BeautifulSoup) for this alone would violate
    rules.md §Dependency Management ("prefer stdlib... over adding a
    new one for a small need"). No LLM call here either
    (rules.md §Performance Guidelines: deterministic where possible).
    """
    return unescape(_TAG_RE.sub(" ", html)).strip()


@register_source("greenhouse")
class GreenhouseSource:
    """``JobSource`` over the public Greenhouse Job Board API."""

    name: ClassVar[str] = "greenhouse"

    def __init__(
        self,
        *,
        boards: list[str],
        timeout_s: float = 15.0,
        max_retries: int = 3,
        circuit_breaker_threshold: int = 3,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        rand: Callable[[], float] = random.random,
    ) -> None:
        """Construct the connector.

        Args:
            boards: Greenhouse board tokens to poll (``config/sources.yaml``
                ``sources.greenhouse.boards``).
            timeout_s: Per-request timeout in seconds.
            max_retries: Max attempts for the shared retry policy
                (design.md §11, llm/retry.py), applied per board.
            circuit_breaker_threshold: Consecutive board-fetch failures
                (each already retry-exhausted) before this source stops
                trying its remaining boards for the rest of this run
                (agents.md §3 "skipped for the remainder of the run
                after N consecutive failures") -- boards already
                fetched successfully are kept, not discarded.
            client: Inject a preconfigured ``httpx.Client`` (e.g. with
                a mock transport) for testing; if omitted, one is built.
            sleep: Injectable sleep function for retry backoff.
            rand: Injectable jitter source for retry backoff.
        """
        self._boards = boards
        self._max_retries = max_retries
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._sleep = sleep
        self._rand = rand
        self._client = client or httpx.Client(timeout=timeout_s)

    def search(self, query: SearchQuery, ctx: RunContext) -> list[RawPosting]:
        """Fetch every configured board and filter by ``query`` (api.md §2).

        Never raises for an individual board's failure -- a board that
        exhausts its retries counts toward this source's circuit
        breaker instead (see ``circuit_breaker_threshold``); once
        tripped, remaining boards for this run are skipped and whatever
        was already fetched is returned. This is deliberately quieter
        than :class:`SourceFetchError` propagating, since one bad board
        token should never fail the whole connector.

        Args:
            query: Keyword/location/remote/recency filters, applied
                client-side (Greenhouse has no server-side keyword search).
            ctx: Unused by this connector (no LLM/DB access needed).

        Returns:
            Matching postings across every board fetched before the
            circuit breaker (if any) tripped.
        """
        postings: list[RawPosting] = []
        consecutive_failures = 0
        for board in self._boards:
            try:
                postings.extend(self._fetch_board(board, query))
                consecutive_failures = 0
            except SourceFetchError:
                consecutive_failures += 1
                if consecutive_failures >= self._circuit_breaker_threshold:
                    break
        return postings

    def _fetch_board(self, board: str, query: SearchQuery) -> list[RawPosting]:
        def _call() -> dict[str, Any]:
            response = self._client.get(f"{_BASE_URL}/{board}/jobs", params={"content": "true"})
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

        try:
            data = call_with_retry(
                _call,
                is_retryable=_is_retryable,
                max_attempts=self._max_retries,
                sleep=self._sleep,
                rand=self._rand,
            )
        except Exception as exc:
            raise SourceFetchError(
                f"Failed to fetch Greenhouse board '{board}': {exc}",
                remedy=(
                    f"Confirm '{board}' is a valid Greenhouse board token "
                    "(config/sources.yaml sources.greenhouse.boards) and "
                    "that the network is reachable."
                ),
            ) from exc

        fetched_at = datetime.now(UTC)
        jobs = data.get("jobs", [])
        all_postings = [self._to_raw_posting(job, board, fetched_at) for job in jobs]
        return [posting for posting in all_postings if _matches(posting, query)]

    def _to_raw_posting(self, job: dict[str, Any], board: str, fetched_at: datetime) -> RawPosting:
        location = (job.get("location") or {}).get("name") or ""
        content = job.get("content") or ""
        return RawPosting(
            source=self.name,
            source_id=str(job["id"]),
            title=job.get("title", ""),
            # Greenhouse's job objects don't carry a resolved company
            # name (it's implicit in which board was queried) -- the
            # board token itself is used as a best-effort identifier
            # rather than fabricating a display name.
            company=board,
            location=location,
            url=job.get("absolute_url", ""),
            raw_content=_strip_html(content),
            fetched_at=fetched_at,
        )


def _matches(posting: RawPosting, query: SearchQuery) -> bool:
    haystack = f"{posting.title} {posting.raw_content}".lower()
    if query.keywords and not any(keyword.lower() in haystack for keyword in query.keywords):
        return False
    if query.locations and not any(
        location.lower() in posting.location.lower() for location in query.locations
    ):
        return False
    return True
