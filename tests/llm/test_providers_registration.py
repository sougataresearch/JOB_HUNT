"""Proves importing jobhunt_core.llm.providers registers all three adapters.

Guards against the plugin-discovery footgun noted in final_review.md
§1.3: a provider class fully correct but never imported would silently
never appear in the registry.
"""

from jobhunt_core.llm.provider import available_providers
from jobhunt_core.llm.providers.anthropic_provider import AnthropicProvider
from jobhunt_core.llm.providers.ollama_provider import OllamaProvider
from jobhunt_core.llm.providers.openai_provider import OpenAIProvider


def test_importing_providers_package_registers_all_three() -> None:
    """All three adapters are registered once jobhunt_core.llm.providers is imported."""
    import jobhunt_core.llm.providers  # noqa: F401

    names = available_providers()

    assert "anthropic" in names
    assert "openai" in names
    assert "ollama" in names


def test_registered_classes_are_the_expected_adapters() -> None:
    """The registry resolves each name to the correct concrete class."""
    from jobhunt_core.llm.provider import get_provider_class

    assert get_provider_class("anthropic") is AnthropicProvider
    assert get_provider_class("openai") is OpenAIProvider
    assert get_provider_class("ollama") is OllamaProvider
