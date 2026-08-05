"""Tests for the prompt loader (api.md §4, prompts.md §Conventions)."""

from pathlib import Path

import pytest

from jobhunt_core.prompts.loader import load_prompt, render_prompt


@pytest.fixture
def prompt_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A scratch prompts/library/ directory, isolated from the real one."""
    import jobhunt_core.prompts.loader as loader_module

    monkeypatch.setattr(loader_module, "PROMPT_LIBRARY_DIR", tmp_path)
    return tmp_path


def _write_prompt(prompt_dir: Path, domain: str, name: str, version: str, body: str) -> None:
    directory = prompt_dir / domain / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{version}.md").write_text(body, encoding="utf-8")


_SAMPLE = """---
name: greet
version: "1.0"
---
## System

You are a friendly assistant.

## User Template

Say hello to {{ user_name }}.
"""


def test_load_prompt_parses_frontmatter_and_sections(prompt_dir: Path) -> None:
    """load_prompt() parses name/version frontmatter and the two body sections."""
    _write_prompt(prompt_dir, "greeting", "greet", "1.0", _SAMPLE)

    template = load_prompt("greeting", "greet", "1.0")

    assert template.name == "greet"
    assert template.version == "1.0"
    assert template.system == "You are a friendly assistant."
    assert template.user_template == "Say hello to {{ user_name }}."


def test_load_prompt_defaults_to_latest_version(prompt_dir: Path) -> None:
    """Omitting version resolves to the highest available version number."""
    _write_prompt(prompt_dir, "greeting", "greet", "1.0", _SAMPLE)
    _write_prompt(
        prompt_dir, "greeting", "greet", "2.0", _SAMPLE.replace('version: "1.0"', 'version: "2.0"')
    )

    template = load_prompt("greeting", "greet")

    assert template.version == "2.0"


def test_load_prompt_missing_directory_raises(prompt_dir: Path) -> None:
    """A domain/name with no version files raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_prompt("nonexistent", "nope")


def test_render_prompt_renders_jinja_and_concatenates_system(prompt_dir: Path) -> None:
    """render_prompt() substitutes variables and prefixes the system text."""
    _write_prompt(prompt_dir, "greeting", "greet", "1.0", _SAMPLE)
    template = load_prompt("greeting", "greet", "1.0")

    rendered = render_prompt(template, user_name="Jane")

    assert rendered == "You are a friendly assistant.\n\nSay hello to Jane."


def test_render_prompt_missing_variable_raises(prompt_dir: Path) -> None:
    """StrictUndefined means a missing template variable raises, not silently renders empty."""
    from jinja2 import UndefinedError

    _write_prompt(prompt_dir, "greeting", "greet", "1.0", _SAMPLE)
    template = load_prompt("greeting", "greet", "1.0")

    with pytest.raises(UndefinedError):
        render_prompt(template)
