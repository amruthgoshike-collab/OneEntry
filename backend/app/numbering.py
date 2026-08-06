"""Sequential human-readable document numbers: JOB-0001, QTN-0001, INV-0001.

Zero-padded to 4 digits so MAX() sorts correctly as text up to 9999 — plenty
for a demo. The unique constraint on each number column is the real guard.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def next_number(db: Session, column, prefix: str, width: int = 4) -> str:
    """Return the next `PREFIX-0001` style number for a numbering column."""
    last = db.execute(select(func.max(column))).scalar()
    seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}-{seq:0{width}d}"
