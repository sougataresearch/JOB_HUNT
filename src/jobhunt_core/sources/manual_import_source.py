"""Manual paste/import connector (tasks.md T7.3, PRD.md §9 ToS fallback).

Structurally different from ``GreenhouseSource``: no live fetch at
all. This is the fallback for any company/board with no public API —
the *human* pastes or downloads the posting themselves, so JOB_HUNT
never fetches third-party content on its own behalf here, sidestepping
the scraping-ToS question entirely (rules.md §Security Rules). Proves
the ``JobSource`` Protocol isn't overfit to API-shaped sources
(implementation_order.md step 24): ``search()`` returns whatever
batch of already-collected items it was constructed with, ignoring
``query`` entirely (there is nothing to filter -- the human already
decided which postings matter).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel

from jobhunt_core.documents.parsers import parser_for_file
from jobhunt_core.schemas.job import RawPosting, SearchQuery
from jobhunt_core.sources.base import register_source

if TYPE_CHECKING:
    # TYPE_CHECKING-only, same rationale as sources/base.py: no runtime
    # dependency on agents/, just a type annotation for the ctx param.
    from jobhunt_core.agents.base import RunContext


class ManualImportItem(BaseModel):
    """One pasted/imported posting (tasks.md T7.3: "a pasted URL/text or file").

    ``url`` is stored as given, never fetched by this connector -- the
    human already has the content in ``raw_content``. Title/company
    extraction from freeform text is deliberately *not* automated here
    (agents.md §3 names an *optional* LLM-assisted normalization step
    for messy manual-paste input; T7.3 is scoped Difficulty: S, so that
    optional step is left for whenever a caller actually needs it, not
    built speculatively now — rules.md AI Coding Rule 2). The caller
    supplies title/company directly, or via :meth:`from_file` for a
    saved posting file.
    """

    url: str
    title: str
    company: str
    location: str = ""
    raw_content: str

    @classmethod
    def from_file(
        cls, path: Path, *, url: str, title: str, company: str, location: str = ""
    ) -> ManualImportItem:
        """Build an item from a saved posting file (PDF/DOCX/Markdown/text).

        Reuses the CV document parsers (``documents/parsers``) for
        raw-text extraction — "get plain text out of a file" isn't a
        CV-specific problem, so no new parsing code is needed here.
        """
        parser = parser_for_file(path)
        parsed = parser.parse(path)
        return cls(
            url=url, title=title, company=company, location=location, raw_content=parsed.raw_text
        )


@register_source("manual_import")
class ManualImportSource:
    """Wraps a fixed, caller-supplied batch of manually-collected postings."""

    name: ClassVar[str] = "manual_import"

    def __init__(self, items: list[ManualImportItem] | None = None) -> None:
        """Construct the connector with whatever items were manually collected this run."""
        self._items = items or []

    def search(self, query: SearchQuery, ctx: RunContext) -> list[RawPosting]:
        """Return every supplied item as a ``RawPosting``, ignoring ``query`` (api.md §2)."""
        return [self._to_raw_posting(item) for item in self._items]

    def _to_raw_posting(self, item: ManualImportItem) -> RawPosting:
        return RawPosting(
            source=self.name,
            source_id=_content_hash(item),
            title=item.title,
            company=item.company,
            location=item.location,
            url=item.url,
            raw_content=item.raw_content,
            fetched_at=datetime.now(UTC),
        )


def _content_hash(item: ManualImportItem) -> str:
    """Deterministic id from content, so re-importing the same paste dedupes cleanly."""
    digest = hashlib.sha256(f"{item.url}|{item.raw_content}".encode()).hexdigest()
    return digest[:32]
