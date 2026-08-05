"""Tests for the layered Settings loader (tasks.md T2.1).

Covers the three-layer precedence required by phases.md Phase 2's
acceptance criteria: defaults -> local.yaml override -> env var.
"""

from pathlib import Path

import pytest
import yaml
from pytest import MonkeyPatch

from jobhunt_core.config.settings import LLMConfig, Settings, load_settings
from jobhunt_core.errors import ConfigError

_LLM_YAML = {
    "llm": {
        "default_provider": "anthropic",
        "providers": {
            "anthropic": {"base_model": "claude-sonnet-5"},
        },
    }
}
_AGENTS_YAML = {
    "agents": {
        "resume_analysis": {"enabled": True, "provider": "anthropic"},
        "job_search": {"enabled": True},
    }
}
_SOURCES_YAML = {
    "sources": {
        "manual_import": {"enabled": True},
    }
}


def _write_default_config(config_dir: Path) -> None:
    (config_dir / "llm.yaml").write_text(yaml.safe_dump(_LLM_YAML))
    (config_dir / "agents.yaml").write_text(yaml.safe_dump(_AGENTS_YAML))
    (config_dir / "sources.yaml").write_text(yaml.safe_dump(_SOURCES_YAML))


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    """A scratch config/ directory with minimal, valid default YAML files."""
    _write_default_config(tmp_path)
    # Isolate from whatever the real developer environment happens to have set.
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "JOBHUNT_LOG_LEVEL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    return tmp_path


def test_loads_defaults_from_yaml(config_dir: Path) -> None:
    """With no local.yaml and no env override, defaults from YAML win."""
    settings = load_settings(config_dir=config_dir, env_file=None)

    assert settings.llm.default_provider == "anthropic"
    assert settings.agents["resume_analysis"].enabled is True
    assert settings.sources["manual_import"].enabled is True
    assert settings.log_level == "INFO"  # dataclass default, no override present


def test_local_yaml_overrides_without_clobbering_siblings(config_dir: Path) -> None:
    """local.yaml overriding one agent leaves sibling agents from defaults intact."""
    local_override = {"agents": {"resume_analysis": {"enabled": False}}}
    (config_dir / "local.yaml").write_text(yaml.safe_dump(local_override))

    settings = load_settings(config_dir=config_dir, env_file=None)

    assert settings.agents["resume_analysis"].enabled is False
    # job_search was not mentioned in local.yaml -- must survive the merge.
    assert settings.agents["job_search"].enabled is True


def test_env_var_overrides_yaml_and_default(config_dir: Path, monkeypatch: MonkeyPatch) -> None:
    """A real environment variable overrides both the YAML-absent field default."""
    monkeypatch.setenv("JOBHUNT_LOG_LEVEL", "DEBUG")

    settings = load_settings(config_dir=config_dir, env_file=None)

    assert settings.log_level == "DEBUG"


def test_env_var_beats_dotenv_file(config_dir: Path, monkeypatch: MonkeyPatch) -> None:
    """A real env var wins over the same key set in a .env file."""
    dotenv_path = config_dir / ".env"
    dotenv_path.write_text("JOBHUNT_LOG_LEVEL=WARNING\n")
    monkeypatch.setenv("JOBHUNT_LOG_LEVEL", "ERROR")

    settings = load_settings(config_dir=config_dir, env_file=dotenv_path)

    assert settings.log_level == "ERROR"


def test_dotenv_file_used_when_no_real_env_var(config_dir: Path, monkeypatch: MonkeyPatch) -> None:
    """With no real env var set, the .env file value is used."""
    dotenv_path = config_dir / ".env"
    dotenv_path.write_text("JOBHUNT_LOG_LEVEL=WARNING\n")
    monkeypatch.delenv("JOBHUNT_LOG_LEVEL", raising=False)

    settings = load_settings(config_dir=config_dir, env_file=dotenv_path)

    assert settings.log_level == "WARNING"


def test_missing_secret_for_enabled_agent_raises_config_error(
    config_dir: Path, monkeypatch: MonkeyPatch
) -> None:
    """An enabled agent needing anthropic with no key set raises ConfigError."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ConfigError) as exc_info:
        load_settings(config_dir=config_dir, env_file=None)

    assert "ANTHROPIC_API_KEY" in str(exc_info.value)
    assert "ANTHROPIC_API_KEY" in exc_info.value.remedy


def test_disabled_agent_does_not_require_secret(config_dir: Path, monkeypatch: MonkeyPatch) -> None:
    """A disabled agent's provider requirement is not enforced."""
    local_override = {"agents": {"resume_analysis": {"enabled": False}}}
    (config_dir / "local.yaml").write_text(yaml.safe_dump(local_override))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    settings = load_settings(config_dir=config_dir, env_file=None)

    assert settings.agents["resume_analysis"].enabled is False


def test_enabled_agent_names_is_sorted_and_excludes_disabled(config_dir: Path) -> None:
    """enabled_agent_names() stands in for an AgentRegistry-level check (T2.3)."""
    local_override = {"agents": {"job_search": {"enabled": False}}}
    (config_dir / "local.yaml").write_text(yaml.safe_dump(local_override))

    settings = load_settings(config_dir=config_dir, env_file=None)

    assert settings.enabled_agent_names() == ["resume_analysis"]


def test_aliased_fields_settable_by_plain_attribute_name(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Settings(data_dir=...) works when constructed directly, not just via env vars.

    Regression test: fields with a validation_alias (data_dir,
    anthropic_api_key, etc.) were previously only settable through
    their env-var alias -- constructing Settings(data_dir=tmp_path)
    directly silently dropped the kwarg (extra="ignore") and fell back
    to the field default, with no error. Caught by a Phase 5 test that
    constructed Settings directly for dependency injection
    (tests/cli/test_setup_command.py); fixed by adding
    populate_by_name=True to Settings.model_config.
    """
    monkeypatch.delenv("JOBHUNT_DATA_DIR", raising=False)

    settings = Settings(
        llm=LLMConfig(default_provider="anthropic", providers={}),
        agents={},
        sources={},
        data_dir=tmp_path,
    )

    assert settings.data_dir == tmp_path
