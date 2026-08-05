"""Prompt template loading and versioning — api.md §4 Prompt API.

Templates themselves live under prompts/library/ at the repo root.
"""

from jobhunt_core.prompts.loader import PromptTemplate, load_prompt, render_prompt

__all__ = ["PromptTemplate", "load_prompt", "render_prompt"]
