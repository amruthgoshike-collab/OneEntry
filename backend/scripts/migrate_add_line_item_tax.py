"""Migration: add line_items.hsn_sac and line_items.tax_rate.

A real Indian GST quotation has to print an HSN/SAC code per line, and lines
can carry different GST rates. `create_all` never adds columns to an existing
table, so a database created before this needs this script.

Safe to re-run and safe on a fresh database.

    cd backend && python -m scripts.migrate_add_line_item_tax
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text

from app.db import engine
from app.models import LineItem  # noqa: F401 — registers the table on Base

TABLE = LineItem.__tablename__
NEW_COLUMNS = {
    "hsn_sac": "VARCHAR(10)",
    "tax_rate": "NUMERIC(5, 2) NOT NULL DEFAULT 18",
}


def main() -> None:
    inspector = inspect(engine)
    if TABLE not in inspector.get_table_names():
        print(f"{TABLE} does not exist yet — run scripts/init_db.py instead.")
        return

    existing = {col["name"] for col in inspector.get_columns(TABLE)}
    missing = {name: ddl for name, ddl in NEW_COLUMNS.items() if name not in existing}
    if not missing:
        print(f"{TABLE} already has {', '.join(NEW_COLUMNS)} — nothing to do.")
        return

    with engine.begin() as conn:
        for name, ddl in missing.items():
            conn.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {name} {ddl}"))
            print(f"Added {TABLE}.{name}.")


if __name__ == "__main__":
    main()
