"""Agent implementations — one module per agent (agents.md).

Importing this package registers every agent (via ``@register_agent``,
orchestration/registry.py) -- the same explicit-import discovery
pattern used for LLM providers, SQLAlchemy models, and CV parsers
(final_review.md §1.3), so a new agent module is added to the import
list below, never left to be found by a filesystem walk.
"""

from jobhunt_core.agents import resume_analysis_agent  # noqa: F401

__all__ = ["resume_analysis_agent"]
