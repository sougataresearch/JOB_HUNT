"""Tests for the JobSource registry (tasks.md T7.1, api.md §9 Plugin API)."""

import pytest

from jobhunt_core.errors import SourceFetchError
from jobhunt_core.schemas.job import RawPosting, SearchQuery
from jobhunt_core.sources.base import (
    _SOURCE_REGISTRY,
    available_sources,
    get_source_class,
    register_source,
)


class _FakeSource:
    """A minimal JobSource-shaped class used only to test the registry."""

    name = "fake"

    def search(self, query: SearchQuery, ctx: object) -> list[RawPosting]:
        """Unused stub -- only the class shape/name matter for this test."""
        return []


@pytest.fixture(autouse=True)
def _clean_registry():
    """Snapshot and restore the module-level registry around each test."""
    original = dict(_SOURCE_REGISTRY)
    yield
    _SOURCE_REGISTRY.clear()
    _SOURCE_REGISTRY.update(original)


def test_register_source_adds_to_registry() -> None:
    """The decorator registers the class under the given name unchanged."""
    decorated = register_source("fake")(_FakeSource)

    assert decorated is _FakeSource
    assert "fake" in available_sources()
    assert get_source_class("fake") is _FakeSource


def test_get_source_class_unregistered_raises_source_fetch_error() -> None:
    """Looking up an unregistered name raises SourceFetchError with a remedy."""
    with pytest.raises(SourceFetchError) as exc_info:
        get_source_class("does-not-exist")

    assert "does-not-exist" in str(exc_info.value)
    assert exc_info.value.remedy


def test_available_sources_is_sorted() -> None:
    """available_sources() returns names in sorted order."""
    register_source("zzz-fake")(_FakeSource)
    register_source("aaa-fake")(_FakeSource)

    names = available_sources()

    assert names == sorted(names)
    assert "zzz-fake" in names
    assert "aaa-fake" in names


def test_greenhouse_and_manual_import_are_registered_by_default() -> None:
    """Importing jobhunt_core.sources registers both Phase 7 connectors."""
    import jobhunt_core.sources  # noqa: F401 -- triggers registration

    assert "greenhouse" in available_sources()
    assert "manual_import" in available_sources()
