"""Job timeline entries.

Every state change on a job writes one of these; the detail screen renders
them as the audit trail that shows the one-entry lineage.
"""
import uuid

from sqlalchemy.orm import Session

from app.models import JobEvent


def log_event(
    db: Session, job_id: uuid.UUID, event_type: str, detail: str | None = None
) -> JobEvent:
    """Add an event to the session. Caller commits."""
    event = JobEvent(job_id=job_id, event_type=event_type, detail=detail)
    db.add(event)
    return event
