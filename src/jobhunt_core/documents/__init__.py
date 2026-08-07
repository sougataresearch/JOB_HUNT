"""Document parsing and rendering: CV ingestion, LaTeX/Jinja2 rendering, and ATS verification.

Importing this package registers every ``DocumentRenderer`` (the same
explicit-import discovery pattern used for LLM providers, sources, and
CV parsers -- final_review.md §1.3), so ``get_renderer_class`` always
has every renderer available once this package has been imported.
"""

from jobhunt_core.documents import renderer  # noqa: F401

__all__ = ["renderer"]
