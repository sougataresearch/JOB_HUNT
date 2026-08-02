"""Shared retry/backoff policy for LLM provider calls (design.md §11).

The backoff algorithm lives here once and is shared by every provider
adapter (rules.md §Performance Guidelines: never reimplement per-agent
or per-provider). What counts as *retryable* differs by SDK/exception
type (429/5xx/timeout yes, 4xx auth/content-policy no), so callers
supply their own classifier rather than this module hardcoding one
SDK's exception hierarchy.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

ResultT = TypeVar("ResultT")

DEFAULT_MAX_ATTEMPTS = 3
"""Total attempts including the first (design.md §11: "max 3 attempts").

Note: config/llm.yaml's per-provider field is named ``max_retries``
for readability, but its value is passed straight through as this
module's ``max_attempts`` (i.e. "max_retries: 3" means 3 total tries,
not 3 retries *after* a first attempt) -- see settings.py's
``ProviderConfig``.
"""

_BASE_DELAY_S = 1.0
_MAX_DELAY_S = 20.0


def call_with_retry(
    func: Callable[[], ResultT],
    *,
    is_retryable: Callable[[Exception], bool],
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
    rand: Callable[[], float] = random.random,
) -> ResultT:
    """Call ``func()``, retrying on retryable errors with backoff + jitter.

    Args:
        func: Zero-argument callable to invoke.
        is_retryable: Predicate deciding whether a raised exception
            should trigger a retry. Never called for the exception
            from the final allowed attempt (there is nothing left to
            retry into).
        max_attempts: Total attempts including the first. Must be
            >= 1.
        sleep: Injectable sleep function, so tests don't actually
            wait.
        rand: Injectable random function returning a float in
            ``[0, 1)``, so tests get deterministic jitter.

    Returns:
        Whatever ``func()`` returns on its first successful attempt.

    Raises:
        Exception: The exception from the final attempt, whenever
            ``max_attempts`` is exhausted or ``is_retryable`` returns
            ``False``.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return func()
        except Exception as exc:
            if attempt >= max_attempts or not is_retryable(exc):
                raise
            delay = min(_BASE_DELAY_S * (2 ** (attempt - 1)), _MAX_DELAY_S)
            jittered_delay = delay * (0.5 + rand() * 0.5)
            sleep(jittered_delay)
