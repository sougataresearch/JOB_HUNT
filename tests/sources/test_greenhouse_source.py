"""Tests for GreenhouseSource (tasks.md T7.2).

No live network calls: an ``httpx.Client`` is built with an
``httpx.MockTransport`` swapped in, the same pattern used for the
Anthropic adapter (tests/llm/providers/test_anthropic_provider.py) --
only the network round-trip is faked.
"""

from collections.abc import Callable

import httpx
import pytest

from jobhunt_core.errors import SourceFetchError
from jobhunt_core.schemas.job import SearchQuery
from jobhunt_core.sources.greenhouse_source import GreenhouseSource


def _client_with_handler(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _job(id_: int, title: str, location: str = "Remote", content: str = "<p>Do stuff.</p>") -> dict:
    return {
        "id": id_,
        "title": title,
        "location": {"name": location},
        "absolute_url": f"https://boards.greenhouse.io/co/jobs/{id_}",
        "content": content,
    }


def test_search_returns_normalized_postings_for_a_board() -> None:
    """A successful board fetch returns RawPostings with HTML content stripped."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jobs": [_job(1, "Backend Engineer")]})

    source = GreenhouseSource(boards=["acme"], client=_client_with_handler(handler))

    postings = source.search(SearchQuery(), ctx=None)  # type: ignore[arg-type]

    assert len(postings) == 1
    assert postings[0].source == "greenhouse"
    assert postings[0].source_id == "1"
    assert postings[0].title == "Backend Engineer"
    assert postings[0].company == "acme"
    assert postings[0].location == "Remote"
    assert "<p>" not in postings[0].raw_content
    assert "Do stuff." in postings[0].raw_content


def test_search_filters_by_keyword() -> None:
    """A posting whose title/content doesn't match any keyword is excluded."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jobs": [
                    _job(1, "Backend Engineer", content="<p>Python and Go.</p>"),
                    _job(2, "Marketing Manager", content="<p>Campaigns and copy.</p>"),
                ]
            },
        )

    source = GreenhouseSource(boards=["acme"], client=_client_with_handler(handler))

    postings = source.search(SearchQuery(keywords=["python"]), ctx=None)  # type: ignore[arg-type]

    assert len(postings) == 1
    assert postings[0].title == "Backend Engineer"


def test_search_filters_by_location() -> None:
    """A posting whose location doesn't match any requested location is excluded."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jobs": [
                    _job(1, "A", location="Berlin"),
                    _job(2, "B", location="Remote - US"),
                ]
            },
        )

    source = GreenhouseSource(boards=["acme"], client=_client_with_handler(handler))

    postings = source.search(SearchQuery(locations=["remote"]), ctx=None)  # type: ignore[arg-type]

    assert len(postings) == 1
    assert postings[0].title == "B"


def test_search_polls_every_configured_board() -> None:
    """Multiple boards are all polled and their postings combined."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        board = request.url.path.split("/")[3]
        calls.append(board)
        return httpx.Response(200, json={"jobs": [_job(1, f"Job at {board}")]})

    source = GreenhouseSource(boards=["acme", "widgetco"], client=_client_with_handler(handler))

    postings = source.search(SearchQuery(), ctx=None)  # type: ignore[arg-type]

    assert calls == ["acme", "widgetco"]
    assert {p.company for p in postings} == {"acme", "widgetco"}


def test_board_404_is_not_retried_and_raises_source_fetch_error() -> None:
    """A 404 (unknown board) is not retryable -- one request, then SourceFetchError."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, json={"error": "not found"})

    source = GreenhouseSource(
        boards=["nonexistent"], max_retries=3, client=_client_with_handler(handler)
    )

    with pytest.raises(SourceFetchError):
        source._fetch_board("nonexistent", SearchQuery())

    assert calls["n"] == 1


def test_board_500_retries_then_succeeds() -> None:
    """A transient 500 followed by a 200 succeeds after a retry, with no real sleep."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(500, json={"error": "oops"})
        return httpx.Response(200, json={"jobs": [_job(1, "Backend Engineer")]})

    source = GreenhouseSource(
        boards=["acme"],
        max_retries=3,
        client=_client_with_handler(handler),
        sleep=lambda _: None,
        rand=lambda: 0.0,
    )

    postings = source.search(SearchQuery(), ctx=None)  # type: ignore[arg-type]

    assert len(postings) == 1
    assert calls["n"] == 2


def test_circuit_breaker_stops_after_n_consecutive_board_failures() -> None:
    """A simulated always-failing source trips the circuit breaker (phases.md Phase 7 AC)."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"error": "always down"})

    boards = ["b1", "b2", "b3", "b4", "b5"]
    source = GreenhouseSource(
        boards=boards,
        max_retries=1,  # 1 attempt per board -> 1 request per board
        circuit_breaker_threshold=2,
        client=_client_with_handler(handler),
        sleep=lambda _: None,
        rand=lambda: 0.0,
    )

    postings = source.search(SearchQuery(), ctx=None)  # type: ignore[arg-type]

    assert postings == []
    # Circuit trips after 2 consecutive failures -- boards b3/b4/b5 never fetched.
    assert calls["n"] == 2


def test_circuit_breaker_resets_on_a_successful_board() -> None:
    """A successful board in between failures resets the consecutive-failure count."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        board = request.url.path.split("/")[3]
        if board == "good":
            return httpx.Response(200, json={"jobs": [_job(1, "Job")]})
        return httpx.Response(500, json={"error": "down"})

    boards = ["bad1", "good", "bad2", "bad3"]
    source = GreenhouseSource(
        boards=boards,
        max_retries=1,
        circuit_breaker_threshold=2,
        client=_client_with_handler(handler),
        sleep=lambda _: None,
        rand=lambda: 0.0,
    )

    postings = source.search(SearchQuery(), ctx=None)  # type: ignore[arg-type]

    # bad1 (fail, count=1), good (success, count resets to 0), bad2+bad3 (fail, count
    # reaches 2 -> circuit trips after bad3, all 4 boards attempted).
    assert len(postings) == 1
    assert calls["n"] == 4
