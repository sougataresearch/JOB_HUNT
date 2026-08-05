"""Prompt template loading and versioning (api.md §4 Prompt API).

On-disk format for files under ``prompts/library/<domain>/<name>/``:

    ---
    name: extract_profile
    version: "1.0"
    ---
    ## System

    <system prompt text>

    ## User Template

    <Jinja2 user-template text>

YAML frontmatter (delimited by ``---``) plus ``## System``/
``## User Template`` headers -- simpler and more robust to parse than
prose-style bold headers, chosen when this loader was implemented
(prompts.md's Conventions section documents this precisely; its
worked examples show prompt *content*, which this format renders
unchanged).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_LIBRARY_DIR = REPO_ROOT / "prompts" / "library"

_SYSTEM_HEADER = "## System"
_USER_HEADER = "## User Template"

# autoescape=False: these are plain-text LLM prompts, not HTML.
_jinja_env = Environment(undefined=StrictUndefined, autoescape=False)


class PromptTemplate(BaseModel):
    """A loaded, versioned prompt template (api.md §4)."""

    name: str
    version: str
    system: str
    user_template: str


def _prompt_dir(agent_domain: str, name: str) -> Path:
    return PROMPT_LIBRARY_DIR / agent_domain / name


def _latest_version(directory: Path) -> str:
    versions = sorted(
        (path.stem for path in directory.glob("*.md")),
        key=lambda v: [int(part) for part in v.split(".")],
    )
    if not versions:
        raise FileNotFoundError(f"No prompt versions found in {directory}")
    return versions[-1]


def _parse_prompt_file(text: str) -> tuple[dict[str, Any], str, str]:
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Prompt file is missing '---' frontmatter delimiters")
    frontmatter = yaml.safe_load(parts[1]) or {}
    body = parts[2]

    if _SYSTEM_HEADER not in body or _USER_HEADER not in body:
        raise ValueError(f"Prompt file is missing '{_SYSTEM_HEADER}'/'{_USER_HEADER}' sections")

    system_idx = body.index(_SYSTEM_HEADER)
    user_idx = body.index(_USER_HEADER)
    system = body[system_idx + len(_SYSTEM_HEADER) : user_idx].strip()
    user_template = body[user_idx + len(_USER_HEADER) :].strip()
    return frontmatter, system, user_template


def load_prompt(agent_domain: str, name: str, version: str | None = None) -> PromptTemplate:
    """Load a prompt template by domain/name/version.

    Args:
        agent_domain: e.g. ``"resume_analysis"``.
        name: e.g. ``"extract_profile"``.
        version: Specific version string (e.g. ``"1.0"``), or ``None``
            for the latest available version.

    Returns:
        The parsed ``PromptTemplate``.
    """
    directory = _prompt_dir(agent_domain, name)
    resolved_version = version if version is not None else _latest_version(directory)
    text = (directory / f"{resolved_version}.md").read_text(encoding="utf-8")
    frontmatter, system, user_template = _parse_prompt_file(text)
    return PromptTemplate(
        name=frontmatter.get("name", name),
        version=str(frontmatter.get("version", resolved_version)),
        system=system,
        user_template=user_template,
    )


def render_prompt(template: PromptTemplate, **variables: Any) -> str:
    """Render a template's system + user portions into one final prompt string.

    Concatenated into a single string (not passed as a separate
    ``system`` parameter) because the Phase 3 ``LLMProvider.complete``/
    ``complete_structured`` signatures only accept one flat ``prompt``
    string -- extending them to a native system-message channel (for
    provider-side prompt caching, config.md's Caching section) is a
    deliberately deferred enhancement, not done here, so Phase 3's
    already-shipped-and-tested adapters aren't reopened for a Phase 5
    nice-to-have (rules.md AI Coding Rule 2).

    Args:
        template: The loaded ``PromptTemplate``.
        **variables: Values substituted into the Jinja2 user template.

    Returns:
        The final prompt string to pass to an ``LLMProvider`` call.
    """
    rendered_user = _jinja_env.from_string(template.user_template).render(**variables)
    return f"{template.system}\n\n{rendered_user}"
