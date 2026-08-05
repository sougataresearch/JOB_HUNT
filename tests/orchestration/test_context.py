"""Tests for orchestration.context (RunContext factory, tasks.md T3.1 deviation note)."""

import pytest
from sqlalchemy.orm import Session

from jobhunt_core.config.settings import AgentConfig, LLMConfig, ProviderConfig, Settings
from jobhunt_core.errors import LLMProviderError
from jobhunt_core.llm.providers.anthropic_provider import AnthropicProvider
from jobhunt_core.orchestration.context import build_llm_provider, build_run_context


def _settings_with_provider(provider_name: str, **provider_cfg_kwargs: object) -> Settings:
    provider_cfg = ProviderConfig(base_model="test-model", **provider_cfg_kwargs)
    return Settings(
        llm=LLMConfig(
            default_provider=provider_name,
            providers={provider_name: provider_cfg},
        ),
        agents={"resume_analysis": AgentConfig(enabled=True, provider=provider_name)},
        sources={},
    )


def test_build_llm_provider_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    """anthropic resolves to a real AnthropicProvider given an API key."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    settings = _settings_with_provider("anthropic")

    provider = build_llm_provider("anthropic", settings)

    assert isinstance(provider, AnthropicProvider)


def test_build_llm_provider_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing ANTHROPIC_API_KEY raises LLMProviderError with a remedy."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = Settings(
        llm=LLMConfig(
            default_provider="anthropic",
            providers={"anthropic": ProviderConfig(base_model="test-model")},
        ),
        agents={},
        sources={},
    )

    with pytest.raises(LLMProviderError) as exc_info:
        build_llm_provider("anthropic", settings)

    assert exc_info.value.remedy


def test_build_llm_provider_missing_config_raises() -> None:
    """A provider with no entry in llm.providers raises LLMProviderError."""
    settings = Settings(
        llm=LLMConfig(default_provider="anthropic", providers={}),
        agents={},
        sources={},
    )

    with pytest.raises(LLMProviderError):
        build_llm_provider("anthropic", settings)


def test_build_run_context_resolves_agent_specific_provider(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The agent's own configured provider is used, not just the global default."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    settings = Settings(
        llm=LLMConfig(
            default_provider="ollama",
            providers={
                "ollama": ProviderConfig(base_model="llama3"),
                "anthropic": ProviderConfig(base_model="claude-sonnet-5"),
            },
        ),
        agents={"resume_analysis": AgentConfig(enabled=True, provider="anthropic")},
        sources={},
    )

    ctx = build_run_context(settings, db_session, agent_name="resume_analysis")

    assert ctx.llm.name == "anthropic"


def test_build_run_context_falls_back_to_default_provider(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An agent with no explicit provider falls back to llm.default_provider."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    settings = Settings(
        llm=LLMConfig(
            default_provider="anthropic",
            providers={"anthropic": ProviderConfig(base_model="claude-sonnet-5")},
        ),
        agents={"job_search": AgentConfig(enabled=True)},
        sources={},
    )

    ctx = build_run_context(settings, db_session, agent_name="job_search")

    assert ctx.llm.name == "anthropic"


def test_build_run_context_bundles_all_six_repositories(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RunContext.repos exposes all 6 repositories (api.md §7 RepositoryBundle)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    settings = _settings_with_provider("anthropic")

    ctx = build_run_context(settings, db_session, agent_name="resume_analysis")

    assert ctx.repos.profiles is not None
    assert ctx.repos.jobs is not None
    assert ctx.repos.matches is not None
    assert ctx.repos.ats is not None
    assert ctx.repos.applications is not None
    assert ctx.repos.interviews is not None
