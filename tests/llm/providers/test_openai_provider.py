"""Tests for the OpenAI LLMProvider adapter (tasks.md T3.3).

No live network calls: a real ``openai.OpenAI`` client is built with an
``httpx.MockTransport`` swapped in, so the SDK's actual request
construction, response parsing, and exception raising all run for
real. Response/error shapes were verified against the installed
openai SDK version directly before being encoded as fixtures (see
progress_log.md).
"""

from collections.abc import Callable

import httpx
import openai
import pytest
from pydantic import BaseModel

from jobhunt_core.llm.providers.openai_provider import OpenAIProvider


class _Thing(BaseModel):
    foo: str
    n: int


def _client_with_handler(handler: Callable[[httpx.Request], httpx.Response]) -> openai.OpenAI:
    # max_retries=0 matches what OpenAIProvider itself sets when it builds its
    # own client -- see the Anthropic adapter tests for why this matters.
    return openai.OpenAI(
        api_key="sk-test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )


def _completion_body(content: str, tokens_in: int = 12, tokens_out: int = 3) -> dict:
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "model": "gpt-5",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": tokens_in,
            "completion_tokens": tokens_out,
            "total_tokens": tokens_in + tokens_out,
        },
    }


def _error_response(status: int, error_type: str, message: str) -> httpx.Response:
    return httpx.Response(
        status, json={"error": {"message": message, "type": error_type, "code": None}}
    )


def test_complete_parses_text_and_usage() -> None:
    """complete() extracts text and token counts from a real SDK response."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_completion_body("hello there"))

    provider = OpenAIProvider(api_key="sk-test", client=_client_with_handler(handler))

    result = provider.complete("hi", model="gpt-5")

    assert result.text == "hello there"
    assert result.tokens_in == 12
    assert result.tokens_out == 3
    assert result.cost_estimate_usd == 0.0


def test_complete_structured_parses_json_schema_response() -> None:
    """complete_structured() sends response_format and validates the JSON content."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion_body('{"foo": "bar", "n": 5}'))

    provider = OpenAIProvider(api_key="sk-test", client=_client_with_handler(handler))

    result = provider.complete_structured("hi", model="gpt-5", response_schema=_Thing)

    assert result.parsed == _Thing(foo="bar", n=5)
    assert captured["body"]["response_format"]["type"] == "json_schema"
    assert captured["body"]["response_format"]["json_schema"]["name"] == "_Thing"


def test_complete_retries_on_rate_limit_then_succeeds() -> None:
    """A 429 followed by a 200 succeeds after one retry, with no real sleep."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return _error_response(429, "rate_limit_error", "slow down")
        return httpx.Response(200, json=_completion_body("ok now"))

    provider = OpenAIProvider(
        api_key="sk-test",
        client=_client_with_handler(handler),
        max_retries=3,
        sleep=lambda _: None,
        rand=lambda: 0.0,
    )

    result = provider.complete("hi", model="gpt-5")

    assert result.text == "ok now"
    assert calls["n"] == 2


def test_complete_does_not_retry_on_auth_error() -> None:
    """A 401 auth error is not retried -- only one request reaches the transport."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _error_response(401, "invalid_request_error", "bad key")

    provider = OpenAIProvider(
        api_key="sk-test", client=_client_with_handler(handler), max_retries=3
    )

    with pytest.raises(openai.AuthenticationError):
        provider.complete("hi", model="gpt-5")

    assert calls["n"] == 1


def test_complete_retries_exhausted_on_persistent_server_error() -> None:
    """A persistent 500 exhausts max_retries and raises the SDK's own error type."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _error_response(500, "server_error", "oops")

    provider = OpenAIProvider(
        api_key="sk-test",
        client=_client_with_handler(handler),
        max_retries=2,
        sleep=lambda _: None,
        rand=lambda: 0.0,
    )

    with pytest.raises(openai.InternalServerError):
        provider.complete("hi", model="gpt-5")

    assert calls["n"] == 2
