"""Migration: add documents.summary.

`create_all` only creates missing tables, never missing columns — so a database
initialised before this column existed needs this script. Safe to re-run and
safe on a fresh database (it no-ops if the column is already there).

    cd backend && python -m scripts.migrate_add_document_summary
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text

from app.db import engine
from app.models import Document  # noqa: F401 — registers the table on Base

COLUMN = "summary"
TABLE = Document.__tablename__


def main() -> None:
    inspector = inspect(engine)
    if TABLE not in inspector.get_table_names():
        print(f"{TABLE} does not exist yet — run scripts/init_db.py instead.")
        return

    existing = {col["name"] for col in inspector.get_columns(TABLE)}
    if COLUMN in existing:
        print(f"{TABLE}.{COLUMN} already exists — nothing to do.")
        return

    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} TEXT"))
    print(f"Added {TABLE}.{COLUMN}.")


if __name__ == "__main__":
    main()
