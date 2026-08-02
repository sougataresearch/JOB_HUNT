"""Anthropic (Claude) LLMProvider adapter (api.md §5, decisions.md ADR-0003)."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import ClassVar, TypeVar

import anthropic
from pydantic import BaseModel

from jobhunt_core.errors import LLMProviderError
from jobhunt_core.llm.provider import register_provider
from jobhunt_core.llm.retry import call_with_retry
from jobhunt_core.llm.types import LLMResponse, StructuredLLMResponse, estimate_cost_usd

SchemaT = TypeVar("SchemaT", bound=BaseModel)

_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APIConnectionError,  # also covers anthropic.APITimeoutError
)

_DEFAULT_MAX_TOKENS = 4096


def _is_retryable(exc: Exception) -> bool:
    """True for 429/5xx/timeout/connection errors; false for 4xx auth/bad-request."""
    return isinstance(exc, _RETRYABLE_EXCEPTIONS)


@register_provider("anthropic")
class AnthropicProvider:
    """LLMProvider adapter over the ``anthropic`` Python SDK."""

    name: ClassVar[str] = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        timeout_s: float = 60.0,
        max_retries: int = 3,
        cost_per_mtok_in: float = 0.0,
        cost_per_mtok_out: float = 0.0,
        client: anthropic.Anthropic | None = None,
        sleep: Callable[[float], None] = time.sleep,
        rand: Callable[[], float] = random.random,
    ) -> None:
        """Construct the adapter.

        Args:
            api_key: Anthropic API key (``ANTHROPIC_API_KEY``).
            timeout_s: Per-request timeout in seconds.
            max_retries: Max attempts for the shared retry policy
                (design.md §11, llm/retry.py). The SDK's own internal
                retries are disabled (``max_retries=0``) so they don't
                double up with jobhunt's retry loop.
            cost_per_mtok_in: USD per 1,000,000 input tokens, from
                ``config/llm.yaml`` (0.0 if unknown).
            cost_per_mtok_out: USD per 1,000,000 output tokens.
            client: Inject a preconfigured ``anthropic.Anthropic``
                client (e.g. with a mock ``httpx`` transport) for
                testing; if omitted, one is built from ``api_key``.
            sleep: Injectable sleep function for retry backoff, so
                tests don't actually wait (llm/retry.py).
            rand: Injectable jitter source for retry backoff.
        """
        self._max_retries = max_retries
        self._cost_per_mtok_in = cost_per_mtok_in
        self._cost_per_mtok_out = cost_per_mtok_out
        self._sleep = sleep
        self._rand = rand
        self._client = client or anthropic.Anthropic(
            api_key=api_key, timeout=timeout_s, max_retries=0
        )

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

        def _call() -> anthropic.types.Message:
            return self._client.messages.create(
                model=model,
                max_tokens=max_tokens or _DEFAULT_MAX_TOKENS,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )

        message = call_with_retry(
            _call,
            is_retryable=_is_retryable,
            max_attempts=self._max_retries,
            sleep=self._sleep,
            rand=self._rand,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        text = "".join(block.text for block in message.content if block.type == "text")
        tokens_in = message.usage.input_tokens
        tokens_out = message.usage.output_tokens
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

        Implemented via forced tool-use: a single tool is derived from
        ``response_schema``'s JSON schema, and ``tool_choice`` forces
        the model to call it, so the ``tool_use`` block's ``input`` *is*
        the structured result — the standard schema-constrained-output
        pattern for Claude models (verified against the real SDK's
        response parsing via a mock transport, not just assumed shape;
        see tests/llm/providers/test_anthropic_provider.py).
        """
        start = time.monotonic()
        tool_name = f"emit_{response_schema.__name__.lower()}"
        tool: anthropic.types.ToolParam = {
            "name": tool_name,
            "description": f"Emit a {response_schema.__name__} result.",
            "input_schema": response_schema.model_json_schema(),
        }

        def _call() -> anthropic.types.Message:
            return self._client.messages.create(
                model=model,
                max_tokens=_DEFAULT_MAX_TOKENS,
                temperature=temperature,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": prompt}],
            )

        message = call_with_retry(
            _call,
            is_retryable=_is_retryable,
            max_attempts=self._max_retries,
            sleep=self._sleep,
            rand=self._rand,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        tool_use_blocks = [block for block in message.content if block.type == "tool_use"]
        if not tool_use_blocks:
            raise LLMProviderError(
                f"Anthropic did not return a tool_use block for forced tool '{tool_name}'.",
                remedy="Retry, or confirm the model supports tool use.",
            )
        parsed = response_schema.model_validate(tool_use_blocks[0].input)

        tokens_in = message.usage.input_tokens
        tokens_out = message.usage.output_tokens
        return StructuredLLMResponse(
            text=str(tool_use_blocks[0].input),
            parsed=parsed,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_estimate_usd=estimate_cost_usd(
                tokens_in, tokens_out, self._cost_per_mtok_in, self._cost_per_mtok_out
            ),
            latency_ms=latency_ms,
        )
