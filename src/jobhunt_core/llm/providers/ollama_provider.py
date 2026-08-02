"""Ollama (local model) LLMProvider adapter -- best-effort (tasks.md T3.4).

Unlike the Anthropic/OpenAI adapters, this one is not verified against
a live Ollama server in this environment (none is available here) --
the request/response shape below follows Ollama's documented
``/api/generate`` REST API from training knowledge, not an empirically
confirmed live response. Treat this adapter as lower-confidence than
the other two until it's been exercised against a real local server
(progress_log.md notes this explicitly).
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from typing import Any, ClassVar, TypeVar

import httpx
from pydantic import BaseModel

from jobhunt_core.errors import LLMProviderError
from jobhunt_core.llm.provider import register_provider
from jobhunt_core.llm.retry import call_with_retry
from jobhunt_core.llm.types import LLMResponse, StructuredLLMResponse, estimate_cost_usd

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _is_retryable(exc: Exception) -> bool:
    """True for timeouts/connection errors/429/5xx; false for other 4xx."""
    if isinstance(exc, httpx.TimeoutException | httpx.ConnectError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


@register_provider("ollama")
class OllamaProvider:
    """LLMProvider adapter over Ollama's local REST API.

    Best-effort (tasks.md T3.4): local models vary widely in how
    reliably they honor a JSON-format constraint, so
    ``complete_structured()`` may raise ``LLMProviderError`` more
    often here than with the hosted providers -- callers should not
    assume parity.
    """

    name: ClassVar[str] = "ollama"

    def __init__(
        self,
        *,
        host: str = "http://localhost:11434",
        timeout_s: float = 120.0,
        max_retries: int = 2,
        cost_per_mtok_in: float = 0.0,
        cost_per_mtok_out: float = 0.0,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        rand: Callable[[], float] = random.random,
    ) -> None:
        """Construct the adapter.

        Args:
            host: Base URL of the Ollama server (``OLLAMA_HOST``).
            timeout_s: Per-request timeout in seconds.
            max_retries: Max attempts for the shared retry policy
                (design.md §11, llm/retry.py).
            cost_per_mtok_in: USD per 1,000,000 input tokens (almost
                always 0.0 for a local model -- kept for interface
                parity with the hosted providers).
            cost_per_mtok_out: USD per 1,000,000 output tokens.
            client: Inject a preconfigured ``httpx.Client`` (e.g. with
                a mock transport) for testing; if omitted, one is
                built from ``host``/``timeout_s``.
            sleep: Injectable sleep function for retry backoff.
            rand: Injectable jitter source for retry backoff.
        """
        self._max_retries = max_retries
        self._cost_per_mtok_in = cost_per_mtok_in
        self._cost_per_mtok_out = cost_per_mtok_out
        self._sleep = sleep
        self._rand = rand
        self._client = client or httpx.Client(base_url=host, timeout=timeout_s)

    def _generate(
        self, *, model: str, prompt: str, temperature: float, response_format: str | None
    ) -> dict[str, Any]:
        def _call() -> dict[str, Any]:
            payload: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature},
            }
            if response_format:
                payload["format"] = response_format
            response = self._client.post("/api/generate", json=payload)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data

        return call_with_retry(
            _call,
            is_retryable=_is_retryable,
            max_attempts=self._max_retries,
            sleep=self._sleep,
            rand=self._rand,
        )

    def complete(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """See ``LLMProvider.complete``.

        ``max_tokens`` is not sent -- Ollama's ``num_predict`` option
        is left at its model default here.
        """
        start = time.monotonic()
        data = self._generate(
            model=model, prompt=prompt, temperature=temperature, response_format=None
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        tokens_in = data.get("prompt_eval_count", 0)
        tokens_out = data.get("eval_count", 0)
        return LLMResponse(
            text=data.get("response", ""),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_estimate_usd=estimate_cost_usd(
                tokens_in, tokens_out, self._cost_per_mtok_in, self._cost_per_mtok_out
            ),
            latency_ms=latency_ms,
        )

    def complete_structured(
        self,
        prompt: str,
        *,
        model: str,
        response_schema: type[SchemaT],
        temperature: float = 0.0,
    ) -> StructuredLLMResponse[SchemaT]:
        """See ``LLMProvider.complete_structured`` (best-effort, see class docstring).

        Uses Ollama's ``format: "json"`` constraint plus an explicit
        schema description in the prompt -- there is no first-class
        schema-enforcement API like Anthropic's tool-use or OpenAI's
        structured outputs for arbitrary local models.
        """
        start = time.monotonic()
        schema_prompt = (
            f"{prompt}\n\nRespond with only valid JSON matching this schema:\n"
            f"{json.dumps(response_schema.model_json_schema())}"
        )
        data = self._generate(
            model=model, prompt=schema_prompt, temperature=temperature, response_format="json"
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        raw_text = data.get("response", "{}")
        try:
            parsed = response_schema.model_validate_json(raw_text)
        except Exception as exc:
            raise LLMProviderError(
                f"Ollama model '{model}' did not return JSON matching {response_schema.__name__}.",
                remedy=(
                    "Try a model with better JSON-following behavior, or reduce schema complexity."
                ),
            ) from exc

        tokens_in = data.get("prompt_eval_count", 0)
        tokens_out = data.get("eval_count", 0)
        return StructuredLLMResponse(
            text=raw_text,
            parsed=parsed,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_estimate_usd=estimate_cost_usd(
                tokens_in, tokens_out, self._cost_per_mtok_in, self._cost_per_mtok_out
            ),
            latency_ms=latency_ms,
        )
