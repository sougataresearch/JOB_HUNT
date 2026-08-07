"""Tests for ManualImportSource (tasks.md T7.3)."""

from pathlib import Path

from jobhunt_core.schemas.job import SearchQuery
from jobhunt_core.sources.manual_import_source import ManualImportItem, ManualImportSource

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "cvs"


def test_search_returns_every_supplied_item_ignoring_query() -> None:
    """search() ignores query filters entirely -- manual import is push-based."""
    item = ManualImportItem(
        url="https://example.com/careers/123",
        title="Senior Backend Engineer",
        company="Example Corp",
        location="Remote",
        raw_content="Full pasted job description text.",
    )
    source = ManualImportSource(items=[item])

    query = SearchQuery(keywords=["nothing-will-match-this"])
    postings = source.search(query, ctx=None)  # type: ignore[arg-type]

    assert len(postings) == 1
    assert postings[0].source == "manual_import"
    assert postings[0].title == "Senior Backend Engineer"
    assert postings[0].company == "Example Corp"
    assert postings[0].url == "https://example.com/careers/123"
    assert postings[0].raw_content == "Full pasted job description text."


def test_search_with_no_items_returns_empty_list() -> None:
    """A default-constructed source (no manually-collected items yet) is a safe no-op."""
    source = ManualImportSource()

    postings = source.search(SearchQuery(), ctx=None)  # type: ignore[arg-type]

    assert postings == []


def test_same_content_produces_the_same_source_id() -> None:
    """Re-importing the same paste produces the same source_id, dedup-ing via JobRepo."""
    item = ManualImportItem(
        url="https://example.com/careers/123",
        title="A",
        company="B",
        raw_content="same text",
    )
    source = ManualImportSource(items=[item, item])

    postings = source.search(SearchQuery(), ctx=None)  # type: ignore[arg-type]

    assert postings[0].source_id == postings[1].source_id


def test_different_content_produces_different_source_ids() -> None:
    """Two distinct pastes get distinct source_ids."""
    item_a = ManualImportItem(
        url="https://a.example.com", title="A", company="X", raw_content="text a"
    )
    item_b = ManualImportItem(
        url="https://b.example.com", title="B", company="Y", raw_content="text b"
    )
    source = ManualImportSource(items=[item_a, item_b])

    postings = source.search(SearchQuery(), ctx=None)  # type: ignore[arg-type]

    assert postings[0].source_id != postings[1].source_id


def test_from_file_extracts_raw_text_via_document_parsers() -> None:
    """from_file() reuses documents/parsers for raw-text extraction (not CV-specific)."""
    item = ManualImportItem.from_file(
        FIXTURES_DIR / "jane_doe_complete.md",
        url="https://example.com/some-posting",
        title="Stand-in Title",
        company="Stand-in Co",
    )

    assert item.url == "https://example.com/some-posting"
    assert "Jane Doe" in item.raw_content
