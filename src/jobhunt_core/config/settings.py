"""Layered configuration loading (config.md, design.md §8).

Precedence, highest to lowest:

1. Environment variables (secrets, CI/deploy overrides) — always win.
2. ``config/local.yaml`` — gitignored, personal overrides.
3. ``config/{llm,agents,sources}.yaml`` — committed defaults.

The two YAML layers are merged with an explicit, recursive dict merge
(``_deep_merge`` below) before ever touching pydantic-settings, then
passed to :class:`Settings` as constructor data. That data has no
field-name overlap with the environment-sourced fields (API keys,
paths, log level), so pydantic-settings' ordinary
init-kwargs-then-env-then-dotenv precedence already yields the layering
above with no need for a custom settings source.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from jobhunt_core.errors import ConfigError

REPO_ROOT = Path(__file__).resolve().parents[3]
"""Repo root, three levels up from src/jobhunt_core/config/settings.py.

JOB_HUNT is run from a cloned checkout, not installed from a package
index (decisions.md ADR-0002's local-first model), so resolving config/
relative to the source tree is the correct default for this project.
"""

DEFAULT_CONFIG_DIR = REPO_ROOT / "config"

_PROVIDER_API_KEY_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    # "ollama" is deliberately absent: it's configured via OLLAMA_HOST,
    # which always has a default (config.md §Environment Variables).
}


class ProviderConfig(BaseModel):
    """One entry under ``llm.providers`` in ``config/llm.yaml``.

    ``cost_per_mtok_in``/``cost_per_mtok_out`` default to 0.0
    (unknown), not a guessed figure — this project has no verified,
    current-as-of-today pricing to hardcode (rules.md AI Coding Rule
    4). Fill them in from the provider's official pricing page if you
    want cost estimates in ``LLMResponse.cost_estimate_usd``
    (phases.md Phase 3 deliverable: "cost/token accounting hook").
    """

    base_model: str
    timeout_s: int = 60
    max_retries: int = 3
    cost_per_mtok_in: float = 0.0
    cost_per_mtok_out: float = 0.0


class LimitsConfig(BaseModel):
    """Cost/call ceilings — config.md §Rate Limits & Cost Ceilings."""

    per_run_max_cost_usd: float = 2.00
    per_day_max_cost_usd: float = 20.00
    per_agent_max_calls_per_run: dict[str, int] = Field(default_factory=dict)


class LLMConfig(BaseModel):
    """The ``llm`` document in ``config/llm.yaml``."""

    default_provider: str
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)


class AgentConfig(BaseModel):
    """One entry under ``agents`` in ``config/agents.yaml`` (feature flags)."""

    enabled: bool = True
    provider: str | None = None
    model: str | None = None


class SourceConfig(BaseModel):
    """One entry under ``sources`` in ``config/sources.yaml``."""

    enabled: bool = True
    rate_limit_per_min: int | None = None


def _read_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file as a dict, or ``{}`` if it doesn't exist or is empty."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    return dict(loaded) if loaded else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into ``base`` without mutating either.

    A plain ``dict.update`` would let a partial override in
    ``local.yaml`` (e.g. one agent's ``enabled`` flag) wipe out every
    sibling key under the same top-level section. Nested dicts are
    merged key-by-key instead so partial overrides stay partial.
    """
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def _load_yaml_config(config_dir: Path) -> dict[str, Any]:
    """Merge the committed YAML defaults with ``local.yaml`` overrides."""
    defaults: dict[str, Any] = {}
    for filename in ("llm.yaml", "agents.yaml", "sources.yaml"):
        defaults = _deep_merge(defaults, _read_yaml(config_dir / filename))
    local_overrides = _read_yaml(config_dir / "local.yaml")
    return _deep_merge(defaults, local_overrides)


class Settings(BaseSettings):
    """The single validated source of truth for all JOB_HUNT config.

    Construct via :func:`load_settings`, not directly, so the
    required-secrets check (config.md §Config Validation Rules) always
    runs.
    """

    llm: LLMConfig
    agents: dict[str, AgentConfig] = Field(default_factory=dict)
    sources: dict[str, SourceConfig] = Field(default_factory=dict)

    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    ollama_host: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_HOST")
    data_dir: Path = Field(default=Path("./data"), validation_alias="JOBHUNT_DATA_DIR")
    log_level: str = Field(default="INFO", validation_alias="JOBHUNT_LOG_LEVEL")
    log_llm_bodies: bool = Field(default=False, validation_alias="JOBHUNT_LOG_LLM_BODIES")
    env: str = Field(default="dev", validation_alias="JOBHUNT_ENV")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def enabled_agent_names(self) -> list[str]:
        """Return the sorted names of agents with ``enabled: true``.

        Stands in for an ``AgentRegistry``-level check
        (tasks.md T2.3) until ``orchestration/registry.py`` exists —
        see progress_log.md for the forward-dependency note.
        """
        return sorted(name for name, cfg in self.agents.items() if cfg.enabled)


def _validate_required_secrets(settings: Settings) -> None:
    """Fail fast if an enabled agent needs a provider with no API key set.

    Only agents with an *explicit* ``provider`` in their config entry
    are considered — an agent with no ``provider`` set (e.g.
    ``job_search``, ``application_tracking`` in config/agents.yaml) is
    treated as not requiring an LLM at all, not as implicitly falling
    back to ``llm.default_provider``. That fallback is a per-agent
    runtime convenience (config.md §Model Selection), not something
    Phase 2's config layer can safely assume applies to every agent
    without agent-level metadata that doesn't exist until Phase 5+.

    Args:
        settings: A constructed, schema-valid ``Settings`` instance.

    Raises:
        ConfigError: A provider explicitly used by at least one
            enabled agent has no corresponding API key configured.
    """
    used_providers = {
        agent_cfg.provider
        for agent_cfg in settings.agents.values()
        if agent_cfg.enabled and agent_cfg.provider is not None
    }

    key_by_provider = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
    }
    for provider in sorted(used_providers):
        env_var = _PROVIDER_API_KEY_ENV_VARS.get(provider)
        if env_var is None:
            continue
        if not key_by_provider.get(provider):
            raise ConfigError(
                f"Provider '{provider}' is used by an enabled agent but {env_var} is not set.",
                remedy=f"Add {env_var} to your .env file (see .env.example).",
            )


def load_settings(
    config_dir: Path = DEFAULT_CONFIG_DIR,
    *,
    env_file: str | Path | None = ".env",
) -> Settings:
    """Load, merge, and validate JOB_HUNT settings.

    Args:
        config_dir: Directory containing ``llm.yaml``, ``agents.yaml``,
            ``sources.yaml``, and an optional ``local.yaml``. Defaults
            to the repo-root ``config/`` directory.
        env_file: Path to a dotenv file, or ``None`` to skip loading
            one (real environment variables are always read
            regardless of this setting).

    Returns:
        A fully validated ``Settings`` instance.

    Raises:
        ConfigError: See :func:`_validate_required_secrets`.
    """
    yaml_data = _load_yaml_config(config_dir)
    settings = Settings(_env_file=env_file, **yaml_data)  # type: ignore[call-arg]
    _validate_required_secrets(settings)
    return settings
