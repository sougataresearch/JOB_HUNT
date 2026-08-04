"""ApplicationRepo — storage access for Application + ApplicationEvent (api.md §7)."""

from __future__ import annotations

import builtins  # see list_events() docstring below

from sqlalchemy.orm import Session

from jobhunt_core.errors import JobHuntError
from jobhunt_core.schemas.application import (
    Application,
    ApplicationEvent,
    ApplicationStatus,
)
from jobhunt_core.storage.models.application import ApplicationEventModel, ApplicationModel


class ApplicationRepo:
    """CRUD access to ``applications``, plus append-only status-event history.

    Status changes must go through :meth:`change_status`, never by
    mutating a fetched ``Application.status`` directly -- that would
    violate the "soft state, hard history" invariant (design.md §3):
    every transition must also produce an ``ApplicationEvent`` row.
    """

    def __init__(self, session: Session) -> None:
        """Wrap a SQLAlchemy session; callers own the transaction boundary."""
        self._session = session

    def get(self, id: str) -> Application | None:
        """Look up an application by id, or ``None`` if it doesn't exist."""
        row = self._session.get(ApplicationModel, id)
        return self._to_schema(row) if row is not None else None

    def get_by_job_posting(self, job_posting_id: str) -> Application | None:
        """Look up the (at most one) application for a posting (database.md §9)."""
        row = (
            self._session.query(ApplicationModel)
            .filter_by(job_posting_id=job_posting_id)
            .one_or_none()
        )
        return self._to_schema(row) if row is not None else None

    def list(self, **filters: object) -> list[Application]:
        """Return all applications matching the given column-value filters."""
        query = self._session.query(ApplicationModel)
        for key, value in filters.items():
            query = query.filter(getattr(ApplicationModel, key) == value)
        return [self._to_schema(row) for row in query.all()]

    def create(self, application: Application) -> Application:
        """Create a new application and its first ``ApplicationEvent``.

        Idempotent per the one-application-per-posting constraint
        (database.md §9, design.md §2): if one already exists for this
        ``job_posting_id``, the existing record is returned unchanged
        rather than raising or duplicating.
        """
        existing = self.get_by_job_posting(application.job_posting_id)
        if existing is not None:
            return existing

        data = application.model_dump(exclude={"id", "created_at", "updated_at", "status"})
        row = ApplicationModel(status=application.status.value, **data)
        self._session.add(row)
        self._session.flush()
        self.add_event(
            row.id,
            ApplicationEvent(application_id=row.id, from_status=None, to_status=application.status),
        )
        return self._to_schema(row)

    def change_status(
        self, application_id: str, to_status: ApplicationStatus, *, note: str | None = None
    ) -> Application:
        """Transition ``status`` and append the corresponding event.

        Args:
            application_id: The application to transition.
            to_status: The new status.
            note: Optional freeform note recorded on the event.

        Returns:
            The updated ``Application``.

        Raises:
            JobHuntError: No application exists with ``application_id``.
        """
        row = self._session.get(ApplicationModel, application_id)
        if row is None:
            raise JobHuntError(f"Application {application_id} not found")
        from_status = ApplicationStatus(row.status)
        row.status = to_status.value
        self._session.flush()
        self.add_event(
            application_id,
            ApplicationEvent(
                application_id=application_id,
                from_status=from_status,
                to_status=to_status,
                note=note,
            ),
        )
        return self._to_schema(row)

    def add_event(self, application_id: str, event: ApplicationEvent) -> None:
        """Append one status-history row. Never updates or deletes existing events."""
        row = ApplicationEventModel(
            application_id=application_id,
            from_status=event.from_status.value if event.from_status else None,
            to_status=event.to_status.value,
            note=event.note,
            source=event.source.value,
        )
        self._session.add(row)
        self._session.flush()

    def list_events(self, application_id: str) -> builtins.list[ApplicationEvent]:
        """Return the full, ordered status history for an application.

        Return type is qualified as ``builtins.list`` because this
        class already defines a method named ``list`` earlier in the
        body -- mypy resolves a bare ``list[...]`` written after that
        point against the method, not the builtin type, and rejects it
        ("Function ... .list is not valid as a type"). Confirmed by
        running mypy, not assumed.
        """
        rows = (
            self._session.query(ApplicationEventModel)
            .filter_by(application_id=application_id)
            .order_by(ApplicationEventModel.occurred_at)
            .all()
        )
        return [self._event_to_schema(row) for row in rows]

    def _to_schema(self, row: ApplicationModel) -> Application:
        return Application(
            id=row.id,
            user_id=row.user_id,
            job_posting_id=row.job_posting_id,
            status=ApplicationStatus(row.status),
            submitted_at=row.submitted_at,
            source_channel=row.source_channel,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _event_to_schema(self, row: ApplicationEventModel) -> ApplicationEvent:
        return ApplicationEvent(
            id=row.id,
            application_id=row.application_id,
            from_status=ApplicationStatus(row.from_status) if row.from_status else None,
            to_status=ApplicationStatus(row.to_status),
            note=row.note,
            occurred_at=row.occurred_at,
            source=row.source,  # type: ignore[arg-type]
        )
