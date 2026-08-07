"""Job source connectors — api.md §2 Job Search API.

Importing this package registers every connector (decisions.md
ADR-0008) -- an explicit list of imports rather than a filesystem-walk
discovery step, so registration is guaranteed to have happened before
any real code calls ``get_source_class`` (final_review.md §1.3).
"""

from jobhunt_core.sources import greenhouse_source, manual_import_source

__all__ = ["greenhouse_source", "manual_import_source"]
