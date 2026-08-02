"""LLM response types shared by every provider adapter (api.md §5)."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMResponse(BaseModel):
    """Common shape returned by ``LLMProvider.complete()``."""

    text: str
    tokens_in: int
    tokens_out: int
    cost_estimate_usd: float
    latency_ms: int


class StructuredLLMResponse(LLMResponse, Generic[SchemaT]):
    """``LLMResponse`` plus the schema-validated parsed object."""

    parsed: SchemaT


def estimate_cost_usd(
    tokens_in: int,
    tokens_out: int,
    cost_per_mtok_in: float,
    cost_per_mtok_out: float,
) -> float:
    """Estimate a call's cost from per-million-token rates.

    Shared by every provider adapter so the formula lives in one
    place. Rates default to 0.0 in ``config/llm.yaml`` when unknown
    (config/settings.py ``ProviderConfig``) — this function does not
    guess a rate on the caller's behalf.

    Args:
        tokens_in: Input/prompt tokens consumed by the call.
        tokens_out: Output/completion tokens produced by the call.
        cost_per_mtok_in: Price in USD per 1,000,000 input tokens.
        cost_per_mtok_out: Price in USD per 1,000,000 output tokens.

    Returns:
        The estimated cost in USD; 0.0 if both rates are 0.0.
    """
    return (tokens_in / 1_000_000) * cost_per_mtok_in + (tokens_out / 1_000_000) * cost_per_mtok_out
