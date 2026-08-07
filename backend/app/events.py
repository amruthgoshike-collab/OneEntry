"""Job timeline entries.

Every state change on a job writes one of these; the detail screen renders
them as the audit trail that shows the one-entry lineage.
"""
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import JobEvent


def log_event(
    db: Session,
    job_id: uuid.UUID,
    event_type: str,
    detail: str | None = None,
    at: datetime | None = None,
) -> JobEvent:
    """Add an event to the session. Caller commits.

    `at` backdates the row — only the seed script uses it, so a demo timeline
    reads as months of history rather than everything happening at once.
    """
    event = JobEvent(job_id=job_id, event_type=event_type, detail=detail)
    if at is not None:
        event.created_at = at
    db.add(event)
    return event
