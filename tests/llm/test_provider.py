"""Tests for the LLMProvider registry (tasks.md T3.1, api.md §9 Plugin API)."""

import pytest

from jobhunt_core.llm.provider import (
    _PROVIDER_REGISTRY,
    available_providers,
    get_provider_class,
    register_provider,
)
from jobhunt_core.llm.types import LLMResponse


class _FakeProvider:
    """A minimal LLMProvider-shaped class used only to test the registry."""

    name = "fake"

    def complete(self, prompt, *, model, temperature=0.0, max_tokens=None):
        """Unused stub -- only the class shape/name matter for this test."""
        return LLMResponse(text="x", tokens_in=1, tokens_out=1, cost_estimate_usd=0.0, latency_ms=1)

    def complete_structured(self, prompt, *, model, response_schema, temperature=0.0):
        """Unused stub -- only the class shape/name matter for this test."""
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _clean_registry():
    """Snapshot and restore the module-level registry around each test."""
    original = dict(_PROVIDER_REGISTRY)
    yield
    _PROVIDER_REGISTRY.clear()
    _PROVIDER_REGISTRY.update(original)


def test_register_provider_adds_to_registry() -> None:
    """The decorator registers the class under the given name unchanged."""
    decorated = register_provider("fake")(_FakeProvider)

    assert decorated is _FakeProvider
    assert "fake" in available_providers()
    assert get_provider_class("fake") is _FakeProvider


def test_get_provider_class_unregistered_raises_llm_provider_error() -> None:
    """Looking up an unregistered name raises LLMProviderError with a remedy."""
    from jobhunt_core.errors import LLMProviderError

    with pytest.raises(LLMProviderError) as exc_info:
        get_provider_class("does-not-exist")

    assert "does-not-exist" in str(exc_info.value)
    assert exc_info.value.remedy


def test_available_providers_is_sorted() -> None:
    """available_providers() returns names in sorted order."""
    register_provider("zzz-fake")(_FakeProvider)
    register_provider("aaa-fake")(_FakeProvider)

    names = available_providers()

    assert names == sorted(names)
    assert "zzz-fake" in names
    assert "aaa-fake" in names
