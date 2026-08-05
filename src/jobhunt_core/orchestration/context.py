"""Builds a RunContext from Settings (architecture.md §6).

The factory that was deliberately deferred in Phase 3's progress_log
entry ("that wiring naturally belongs where RunContext is built...
Phase 5+") -- Phase 5 is where the first agent needs it.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from jobhunt_core.agents.base import RepositoryBundle, RunContext
from jobhunt_core.config.settings import Settings
from jobhunt_core.errors import LLMProviderError
from jobhunt_core.llm import providers as _providers  # noqa: F401 -- registers adapters
from jobhunt_core.llm.provider import LLMProvider, get_provider_class
from jobhunt_core.storage.repositories import (
    ApplicationRepo,
    ATSRepo,
    InterviewRepo,
    JobRepo,
    MatchRepo,
    ProfileRepo,
)


def build_llm_provider(provider_name: str, settings: Settings) -> LLMProvider:
    """Construct a configured ``LLMProvider`` instance for ``provider_name``.

    A small, explicit if/elif dispatch rather than a generic
    ``from_settings()`` classmethod convention across providers --
    with only 3 known providers and differing constructor needs (API
    key vs. host), this stays simpler than that abstraction would be
    (rules.md no-speculative-abstraction). Revisit if a 4th provider
    makes the dispatch unwieldy.

    Args:
        provider_name: e.g. ``"anthropic"``.
        settings: The loaded application settings.

    Returns:
        A constructed, ready-to-use ``LLMProvider``.

    Raises:
        LLMProviderError: No config exists for ``provider_name``, its
            required API key is not set, or the name is unrecognized.
    """
    provider_cls = get_provider_class(provider_name)
    provider_cfg = settings.llm.providers.get(provider_name)
    if provider_cfg is None:
        raise LLMProviderError(
            f"No provider config found for '{provider_name}' in llm.yaml.",
            remedy="Add an entry under llm.providers in config/llm.yaml.",
        )

    if provider_name == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMProviderError(
                "ANTHROPIC_API_KEY is not set.", remedy="Add it to your .env file."
            )
        return provider_cls(  # type: ignore[call-arg]
            api_key=settings.anthropic_api_key,
            timeout_s=provider_cfg.timeout_s,
            max_retries=provider_cfg.max_retries,
            cost_per_mtok_in=provider_cfg.cost_per_mtok_in,
            cost_per_mtok_out=provider_cfg.cost_per_mtok_out,
        )
    if provider_name == "openai":
        if not settings.openai_api_key:
            raise LLMProviderError("OPENAI_API_KEY is not set.", remedy="Add it to your .env file.")
        return provider_cls(  # type: ignore[call-arg]
            api_key=settings.openai_api_key,
            timeout_s=provider_cfg.timeout_s,
            max_retries=provider_cfg.max_retries,
            cost_per_mtok_in=provider_cfg.cost_per_mtok_in,
            cost_per_mtok_out=provider_cfg.cost_per_mtok_out,
        )
    if provider_name == "ollama":
        return provider_cls(  # type: ignore[call-arg]
            host=settings.ollama_host,
            timeout_s=provider_cfg.timeout_s,
            max_retries=provider_cfg.max_retries,
            cost_per_mtok_in=provider_cfg.cost_per_mtok_in,
            cost_per_mtok_out=provider_cfg.cost_per_mtok_out,
        )
    raise LLMProviderError(f"Unknown provider '{provider_name}'.")


def build_repository_bundle(session: Session) -> RepositoryBundle:
    """Construct a ``RepositoryBundle``, all repositories sharing one session."""
    return RepositoryBundle(
        profiles=ProfileRepo(session),
        jobs=JobRepo(session),
        matches=MatchRepo(session),
        ats=ATSRepo(session),
        applications=ApplicationRepo(session),
        interviews=InterviewRepo(session),
    )


def build_run_context(settings: Settings, session: Session, *, agent_name: str) -> RunContext:
    """Construct a ``RunContext`` for running ``agent_name``.

    Args:
        settings: The loaded application settings.
        session: An open SQLAlchemy session.
        agent_name: The agent this context will be used to run, e.g.
            ``"resume_analysis"`` -- used to resolve which provider to
            build (the agent's own config, falling back to
            ``llm.default_provider``).

    Returns:
        A ready-to-use ``RunContext``.
    """
    agent_cfg = settings.agents.get(agent_name)
    provider_name = (agent_cfg.provider if agent_cfg else None) or settings.llm.default_provider
    llm = build_llm_provider(provider_name, settings)
    repos = build_repository_bundle(session)
    return RunContext(settings=settings, llm=llm, repos=repos)
