"""Job Search Agent — SearchQuery to deduped list[JobPosting] (agents.md §3).

Third agent in the core pipeline (architecture.md §3.1): queries every
enabled ``JobSource``, normalizes ``RawPosting -> JobPosting``, and
dedupes on two layers (database.md §5):

1. **Primary** — unique ``(source, source_id)``: a re-run with
   overlapping results never inserts the same posting twice.
2. **Secondary (fuzzy)** — normalized ``(company, title, location)`` +
   a content hash: flags *likely* cross-source duplicates as a
   warning (``AgentResult.warnings``) without merging or dropping them
   automatically (database.md §5 "flags... without merging").

No prompt/LLM call: sourcing and normalization are deterministic
(agents.md §3 "Prompt template: None required for sourcing itself").
"""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, Field

from jobhunt_core.agents.base import AgentResult, RunContext
from jobhunt_core.errors import SourceFetchError
from jobhunt_core.orchestration.registry import register_agent
from jobhunt_core.schemas.job import JobPosting, RawPosting, RemoteType, SearchQuery, SearchRun


class JobSearchResult(BaseModel):
    """Wraps the Job Search Agent's output list for ``AgentResult``'s ``BaseModel`` bound.

    agents.md §3 documents the output simply as ``list[JobPosting]`` --
    ``AgentResult[OutT]`` requires ``OutT`` to itself be a
    ``BaseModel`` (a bare ``list`` doesn't satisfy that TypeVar bound),
    so this thin wrapper is the same kind of necessary, disclosed
    adaptation as Phase 5's ``CandidateProfileExtraction`` narrowing.
    """

    postings: list[JobPosting] = Field(default_factory=list)
    search_run_id: str | None = None


@register_agent("job_search")
class JobSearchAgent:
    """Sources postings from every enabled ``JobSource`` and dedupes them."""

    name: ClassVar[str] = "job_search"
    input_schema: ClassVar[type[BaseModel]] = SearchQuery
    output_schema: ClassVar[type[BaseModel]] = JobSearchResult

    def run(self, input: SearchQuery, ctx: RunContext) -> AgentResult[JobSearchResult]:
        """Query every enabled source, normalize, dedupe, and persist new postings.

        Per-source isolation (design.md §10): a source whose
        ``search()`` raises ``SourceFetchError`` is caught, logged as a
        warning, and skipped -- the remaining sources are still queried
        (distinct from an individual connector's own internal circuit
        breaker, e.g. ``GreenhouseSource``'s per-board one).

        Args:
            input: Keyword/location/remote/recency filters for this run.
            ctx: Run context -- ``ctx.sources`` supplies every enabled
                ``JobSource`` (``orchestration.context.build_sources()``).

        Returns:
            An ``AgentResult`` wrapping the newly-inserted postings
            (already-seen postings are recognized, not re-returned).
        """
        start = time.monotonic()
        warnings: list[str] = []

        search_run = ctx.repos.jobs.create_search_run(
            SearchRun(
                query=input,
                sources_queried=sorted(ctx.sources),
                started_at=datetime.now(UTC),
            )
        )
        assert search_run.id is not None  # always set: create_search_run just flushed this row

        existing_postings = ctx.repos.jobs.list()
        new_postings: list[JobPosting] = []
        total_found = 0

        for source_name, source in ctx.sources.items():
            try:
                raw_postings = source.search(input, ctx)
            except SourceFetchError as exc:
                warnings.append(f"Source '{source_name}' failed and was skipped: {exc}")
                continue

            for raw in raw_postings:
                total_found += 1
                if ctx.repos.jobs.get_by_source(raw.source, raw.source_id) is not None:
                    continue  # primary dedup: already have this exact posting

                posting = _normalize(raw, search_run.id)
                # Resolved before the fuzzy-dedup key so both sides compare the
                # same kind of value (company identity via get-or-create-by-
                # exact-name), not a raw company-name string against an id.
                company = ctx.repos.jobs.get_or_create_company(raw.company)
                posting.company_id = company.id

                duplicate = _find_fuzzy_duplicate(posting, existing_postings)
                if duplicate is not None:
                    warnings.append(
                        f"Posting '{posting.title}' from '{posting.source}' looks like a "
                        f"likely duplicate of existing posting {duplicate.id} from "
                        f"'{duplicate.source}' (matching company/title/location + content) "
                        "-- kept as a separate row, not merged."
                    )

                saved = ctx.repos.jobs.save(posting)
                new_postings.append(saved)
                existing_postings.append(saved)

        ctx.repos.jobs.complete_search_run(
            search_run.id, postings_found=total_found, postings_deduped_new=len(new_postings)
        )

        latency_ms = int((time.monotonic() - start) * 1000)
        return AgentResult(
            output=JobSearchResult(postings=new_postings, search_run_id=search_run.id),
            prompt_version="n/a",
            model="n/a",
            latency_ms=latency_ms,
            warnings=warnings,
        )


def _normalize(raw: RawPosting, search_run_id: str | None) -> JobPosting:
    """``RawPosting`` -> unsaved ``JobPosting`` (agents.md §3 normalize step).

    ``raw.raw_content`` is already source-cleaned plain text (each
    connector knows its own content format best, e.g.
    ``GreenhouseSource`` strips HTML before returning it) -- this step
    is a schema reshape plus timestamps, not further content cleaning.
    """
    return JobPosting(
        source=raw.source,
        source_id=raw.source_id,
        title=raw.title,
        location=raw.location or None,
        remote_type=_infer_remote_type(raw.location),
        url=raw.url,
        normalized_description=raw.raw_content,
        discovered_at=datetime.now(UTC),
        search_run_id=search_run_id,
    )


def _infer_remote_type(location: str) -> RemoteType:
    """A deterministic keyword heuristic, not a guess about unstated facts.

    Only classifies REMOTE/HYBRID when the location text says so
    explicitly -- never infers ONSITE from a bare location string,
    since that's a positive claim the text doesn't support (rules.md
    AI Coding Rule 1's spirit applied to a non-LLM heuristic).
    """
    lowered = location.lower()
    if "remote" in lowered:
        return RemoteType.REMOTE
    if "hybrid" in lowered:
        return RemoteType.HYBRID
    return RemoteType.UNKNOWN


def _dedup_key(posting: JobPosting) -> str:
    """Normalized ``(company, title, location)`` + content hash (database.md §5).

    Uses ``company_id`` (not the raw company-name string) for the
    company component: ``JobRepo.get_or_create_company`` already
    resolves both sides to the same id for an exact-name match, and
    comparing ids -- rather than re-normalizing two possibly
    differently-cased/spelled name strings -- avoids a raw-string-vs-id
    mismatch bug and keeps this deterministic and simple (rules.md
    no-speculative-abstraction: no fuzzy string-similarity matching
    beyond what "normalized" plainly requires).
    """
    parts = (posting.company_id or "", posting.title, posting.location or "")
    normalized = "|".join(part.strip().lower() for part in parts)
    content_hash = hashlib.sha256(posting.normalized_description.encode()).hexdigest()
    return f"{normalized}::{content_hash}"


def _find_fuzzy_duplicate(posting: JobPosting, existing: list[JobPosting]) -> JobPosting | None:
    """Return an existing posting that looks like the same job from a different source.

    Cross-source only (database.md §5 "flags likely-duplicates across
    sources") -- a same-source match is already handled by the primary
    ``(source, source_id)`` dedup key before this is ever called.
    """
    key = _dedup_key(posting)
    for candidate in existing:
        if candidate.source == posting.source:
            continue
        if _dedup_key(candidate) == key:
            return candidate
    return None
