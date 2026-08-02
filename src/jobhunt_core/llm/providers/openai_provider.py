"""OpenAI LLMProvider adapter (api.md §5, decisions.md ADR-0003)."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any, ClassVar, TypeVar

import openai
from pydantic import BaseModel

from jobhunt_core.llm.provider import register_provider
from jobhunt_core.llm.retry import call_with_retry
from jobhunt_core.llm.types import LLMResponse, StructuredLLMResponse, estimate_cost_usd

SchemaT = TypeVar("SchemaT", bound=BaseModel)

_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    openai.RateLimitError,
    openai.InternalServerError,
    openai.APIConnectionError,  # also covers openai.APITimeoutError
)


def _is_retryable(exc: Exception) -> bool:
    """True for 429/5xx/timeout/connection errors; false for 4xx auth/bad-request."""
    return isinstance(exc, _RETRYABLE_EXCEPTIONS)


@register_provider("openai")
class OpenAIProvider:
    """LLMProvider adapter over the ``openai`` Python SDK."""

    name: ClassVar[str] = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        timeout_s: float = 60.0,
        max_retries: int = 3,
        cost_per_mtok_in: float = 0.0,
        cost_per_mtok_out: float = 0.0,
        client: openai.OpenAI | None = None,
        sleep: Callable[[float], None] = time.sleep,
        rand: Callable[[], float] = random.random,
    ) -> None:
        """Construct the adapter.

        Args: see ``AnthropicProvider`` for the shared rationale
            (same shared retry policy, same cost-accounting fields).
        """
        self._max_retries = max_retries
        self._cost_per_mtok_in = cost_per_mtok_in
        self._cost_per_mtok_out = cost_per_mtok_out
        self._sleep = sleep
        self._rand = rand
        self._client = client or openai.OpenAI(api_key=api_key, timeout=timeout_s, max_retries=0)

    def complete(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """See ``LLMProvider.complete``."""
        start = time.monotonic()

        def _call() -> openai.types.chat.ChatCompletion:
            return self._client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )

        completion = call_with_retry(
            _call,
            is_retryable=_is_retryable,
            max_attempts=self._max_retries,
            sleep=self._sleep,
            rand=self._rand,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        text = completion.choices[0].message.content or ""
        tokens_in = completion.usage.prompt_tokens if completion.usage else 0
        tokens_out = completion.usage.completion_tokens if completion.usage else 0
        return LLMResponse(
            text=text,
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
        """See ``LLMProvider.complete_structured``.

        Uses OpenAI's Structured Outputs (``response_format`` with a
        ``json_schema``) so the returned content is guaranteed to
        validate against ``response_schema`` (verified against the
        real SDK's request/response handling via a mock transport, not
        just assumed shape; see
        tests/llm/providers/test_openai_provider.py).
        """
        start = time.monotonic()
        schema: dict[str, Any] = response_schema.model_json_schema()
        schema["additionalProperties"] = False

        def _call() -> openai.types.chat.ChatCompletion:
            return self._client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_schema.__name__,
                        "schema": schema,
                        "strict": True,
                    },
                },
            )

        completion = call_with_retry(
            _call,
            is_retryable=_is_retryable,
            max_attempts=self._max_retries,
            sleep=self._sleep,
            rand=self._rand,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        raw_text = completion.choices[0].message.content or "{}"
        parsed = response_schema.model_validate_json(raw_text)
        tokens_in = completion.usage.prompt_tokens if completion.usage else 0
        tokens_out = completion.usage.completion_tokens if completion.usage else 0
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
