"""Tests for the shared retry/backoff policy (tasks.md T3.5)."""

import pytest

from jobhunt_core.llm.retry import call_with_retry


class _RetryableError(Exception):
    """Stands in for a 429/5xx/timeout-shaped error in these tests."""


class _NonRetryableError(Exception):
    """Stands in for a 4xx auth/content-policy-shaped error in these tests."""


def _always_retryable(exc: Exception) -> bool:
    return isinstance(exc, _RetryableError)


def test_succeeds_on_first_attempt_without_sleeping() -> None:
    """A function that succeeds immediately is called exactly once."""
    calls = []
    sleeps: list[float] = []

    def func() -> str:
        calls.append(1)
        return "ok"

    result = call_with_retry(
        func, is_retryable=_always_retryable, sleep=sleeps.append, rand=lambda: 0.0
    )

    assert result == "ok"
    assert len(calls) == 1
    assert sleeps == []


def test_retries_on_retryable_error_then_succeeds() -> None:
    """A retryable failure is retried and the eventual success is returned."""
    attempts = {"n": 0}
    sleeps: list[float] = []

    def func() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _RetryableError("simulated 429")
        return "ok"

    result = call_with_retry(
        func,
        is_retryable=_always_retryable,
        max_attempts=3,
        sleep=sleeps.append,
        rand=lambda: 0.0,
    )

    assert result == "ok"
    assert attempts["n"] == 3
    assert len(sleeps) == 2  # slept before attempt 2 and attempt 3


def test_exhausts_max_attempts_and_raises() -> None:
    """After max_attempts, the last exception propagates."""
    attempts = {"n": 0}

    def func() -> str:
        attempts["n"] += 1
        raise _RetryableError(f"attempt {attempts['n']}")

    with pytest.raises(_RetryableError, match="attempt 3"):
        call_with_retry(
            func,
            is_retryable=_always_retryable,
            max_attempts=3,
            sleep=lambda _: None,
            rand=lambda: 0.0,
        )

    assert attempts["n"] == 3


def test_non_retryable_error_raises_immediately() -> None:
    """A non-retryable error is never retried, even with attempts remaining."""
    attempts = {"n": 0}
    sleeps: list[float] = []

    def func() -> str:
        attempts["n"] += 1
        raise _NonRetryableError("simulated 401")

    with pytest.raises(_NonRetryableError):
        call_with_retry(
            func,
            is_retryable=_always_retryable,
            max_attempts=3,
            sleep=sleeps.append,
            rand=lambda: 0.0,
        )

    assert attempts["n"] == 1
    assert sleeps == []


def test_backoff_is_exponential_with_jitter() -> None:
    """Delay grows roughly exponentially and stays within the jitter band."""
    sleeps: list[float] = []

    def func() -> str:
        raise _RetryableError("always fails")

    with pytest.raises(_RetryableError):
        call_with_retry(
            func,
            is_retryable=_always_retryable,
            max_attempts=4,
            sleep=sleeps.append,
            rand=lambda: 1.0,  # max jitter multiplier (1.0)
        )

    # Base delays before attempts 2, 3, 4 are 1s, 2s, 4s; jitter at
    # rand()=1.0 multiplies by (0.5 + 1.0*0.5) = 1.0, so delays are exact.
    assert sleeps == pytest.approx([1.0, 2.0, 4.0])
