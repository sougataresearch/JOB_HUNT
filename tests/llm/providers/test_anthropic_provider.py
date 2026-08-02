"""Tests for the Anthropic LLMProvider adapter (tasks.md T3.2).

No live network calls: a real ``anthropic.Anthropic`` client is built
with an ``httpx.MockTransport`` swapped in for the HTTP layer, so the
SDK's actual request construction, response parsing, and exception
raising all run for real -- only the network round-trip is faked. The
response/error JSON shapes below were verified against the installed
anthropic SDK version directly (not just assumed) before being encoded
here as fixtures; see progress_log.md for how.
"""

from collections.abc import Callable

import anthropic
import httpx
import pytest
from pydantic import BaseModel

from jobhunt_core.errors import LLMProviderError
from jobhunt_core.llm.providers.anthropic_provider import AnthropicProvider


class _Thing(BaseModel):
    foo: str
    n: int


def _client_with_handler(handler: Callable[[httpx.Request], httpx.Response]) -> anthropic.Anthropic:
    # max_retries=0 matches what AnthropicProvider itself sets when it builds
    # its own client (see anthropic_provider.py) -- without this, the SDK's
    # own default internal retries (max_retries=2) compound with
    # call_with_retry's attempts, which is exactly the double-retry problem
    # the adapter is designed to avoid. Confirmed by this test suite: an
    # earlier version of this helper omitted it and produced 6 requests
    # instead of the expected 2 for a 2-attempt retry policy.
    return anthropic.Anthropic(
        api_key="sk-test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )


def _text_response_body(text: str, tokens_in: int = 12, tokens_out: int = 3) -> dict:
    return {
        "id": "msg_123",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": tokens_in, "output_tokens": tokens_out},
    }


def _tool_use_response_body(
    tool_name: str, input_dict: dict, tokens_in: int = 20, tokens_out: int = 8
) -> dict:
    return {
        "id": "msg_123",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5",
        "content": [{"type": "tool_use", "id": "toolu_1", "name": tool_name, "input": input_dict}],
        "stop_reason": "tool_use",
        "stop_sequence": None,
        "usage": {"input_tokens": tokens_in, "output_tokens": tokens_out},
    }


def _error_response(status: int, error_type: str, message: str) -> httpx.Response:
    return httpx.Response(
        status, json={"type": "error", "error": {"type": error_type, "message": message}}
    )


def test_complete_parses_text_and_usage() -> None:
    """complete() extracts text and token counts from a real SDK response."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_text_response_body("hello there"))

    provider = AnthropicProvider(api_key="sk-test", client=_client_with_handler(handler))

    result = provider.complete("hi", model="claude-sonnet-5")

    assert result.text == "hello there"
    assert result.tokens_in == 12
    assert result.tokens_out == 3
    assert result.cost_estimate_usd == 0.0  # no cost_per_mtok configured
    assert result.latency_ms >= 0


def test_complete_structured_parses_tool_use_input() -> None:
    """complete_structured() forces tool use and validates the tool input."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = _tool_use_response_body("emit_thing", {"foo": "bar", "n": 5})
        return httpx.Response(200, json=body)

    provider = AnthropicProvider(api_key="sk-test", client=_client_with_handler(handler))

    result = provider.complete_structured("hi", model="claude-sonnet-5", response_schema=_Thing)

    assert result.parsed == _Thing(foo="bar", n=5)
    assert result.tokens_in == 20
    assert result.tokens_out == 8


def test_complete_structured_raises_when_no_tool_use_block() -> None:
    """A response with no tool_use block raises LLMProviderError, not a crash."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_text_response_body("I refuse to use the tool"))

    provider = AnthropicProvider(api_key="sk-test", client=_client_with_handler(handler))

    with pytest.raises(LLMProviderError):
        provider.complete_structured("hi", model="claude-sonnet-5", response_schema=_Thing)


def test_complete_retries_on_rate_limit_then_succeeds() -> None:
    """A 429 followed by a 200 succeeds after one retry, with no real sleep."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return _error_response(429, "rate_limit_error", "slow down")
        return httpx.Response(200, json=_text_response_body("ok now"))

    provider = AnthropicProvider(
        api_key="sk-test",
        client=_client_with_handler(handler),
        max_retries=3,
        sleep=lambda _: None,
        rand=lambda: 0.0,
    )

    result = provider.complete("hi", model="claude-sonnet-5")

    assert result.text == "ok now"
    assert calls["n"] == 2


def test_complete_does_not_retry_on_auth_error() -> None:
    """A 401 auth error is not retried -- only one request reaches the transport."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _error_response(401, "authentication_error", "bad key")

    provider = AnthropicProvider(
        api_key="sk-test", client=_client_with_handler(handler), max_retries=3
    )

    with pytest.raises(anthropic.AuthenticationError):
        provider.complete("hi", model="claude-sonnet-5")

    assert calls["n"] == 1


def test_complete_retries_exhausted_on_persistent_server_error() -> None:
    """A persistent 500 exhausts max_retries and raises the SDK's own error type."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _error_response(500, "api_error", "oops")

    provider = AnthropicProvider(
        api_key="sk-test",
        client=_client_with_handler(handler),
        max_retries=2,
        sleep=lambda _: None,
        rand=lambda: 0.0,
    )

    with pytest.raises(anthropic.InternalServerError):
        provider.complete("hi", model="claude-sonnet-5")

    assert calls["n"] == 2
