"""Tests for the Ollama LLMProvider adapter (tasks.md T3.4, best-effort).

Uses a plain ``httpx.Client`` with a ``httpx.MockTransport`` -- no
vendor SDK is involved for this adapter (it talks to Ollama's REST API
directly), so these tests exercise the adapter's own request/response
handling end to end, with no live network calls.
"""

import json
from collections.abc import Callable

import httpx
import pytest
from pydantic import BaseModel

from jobhunt_core.errors import LLMProviderError
from jobhunt_core.llm.providers.ollama_provider import OllamaProvider


class _Thing(BaseModel):
    foo: str
    n: int


def _client_with_handler(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(base_url="http://localhost:11434", transport=httpx.MockTransport(handler))


def _generate_body(response_text: str, prompt_eval_count: int = 10, eval_count: int = 4) -> dict:
    return {
        "model": "llama3",
        "created_at": "2026-08-02T00:00:00Z",
        "response": response_text,
        "done": True,
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
    }


def test_complete_parses_text_and_usage() -> None:
    """complete() extracts text and token counts from an /api/generate response."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        body = json.loads(request.content)
        assert body["stream"] is False
        return httpx.Response(200, json=_generate_body("hello there"))

    provider = OllamaProvider(client=_client_with_handler(handler))

    result = provider.complete("hi", model="llama3")

    assert result.text == "hello there"
    assert result.tokens_in == 10
    assert result.tokens_out == 4


def test_complete_structured_parses_json_response() -> None:
    """complete_structured() requests JSON format and validates the content."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_generate_body('{"foo": "bar", "n": 5}'))

    provider = OllamaProvider(client=_client_with_handler(handler))

    result = provider.complete_structured("hi", model="llama3", response_schema=_Thing)

    assert result.parsed == _Thing(foo="bar", n=5)
    assert captured["body"]["format"] == "json"


def test_complete_structured_raises_on_invalid_json() -> None:
    """A model that ignores the JSON constraint raises LLMProviderError, not a crash."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_generate_body("not valid json at all"))

    provider = OllamaProvider(client=_client_with_handler(handler))

    with pytest.raises(LLMProviderError):
        provider.complete_structured("hi", model="llama3", response_schema=_Thing)


def test_complete_retries_on_503_then_succeeds() -> None:
    """A 503 followed by a 200 succeeds after one retry, with no real sleep."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503, text="server overloaded")
        return httpx.Response(200, json=_generate_body("ok now"))

    provider = OllamaProvider(
        client=_client_with_handler(handler),
        max_retries=3,
        sleep=lambda _: None,
        rand=lambda: 0.0,
    )

    result = provider.complete("hi", model="llama3")

    assert result.text == "ok now"
    assert calls["n"] == 2


def test_complete_does_not_retry_on_404() -> None:
    """A 404 (e.g. unknown model) is not retried."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, text="model not found")

    provider = OllamaProvider(
        client=_client_with_handler(handler),
        max_retries=3,
        sleep=lambda _: None,
        rand=lambda: 0.0,
    )

    with pytest.raises(httpx.HTTPStatusError):
        provider.complete("hi", model="does-not-exist")

    assert calls["n"] == 1
