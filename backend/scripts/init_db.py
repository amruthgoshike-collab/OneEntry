"""Create all tables and the v_search view against DATABASE_URL.

Re-runnable: create_all skips existing tables, the view is CREATE OR REPLACE.

    cd backend && python -m scripts.init_db
"""
import sys
from pathlib import Path

# Allow running as a plain script (python scripts/init_db.py) too.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text

from app.db import Base, engine
from app.models import SEARCH_VIEW_SQL  # importing registers all models on Base


def main() -> None:
    print(f"Connecting to {engine.url.render_as_string(hide_password=True)}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(SEARCH_VIEW_SQL))

    inspector = inspect(engine)
    print("\nTables:")
    for table in sorted(inspector.get_table_names()):
        print(f"  {table}")
    print("\nViews:")
    for view in sorted(inspector.get_view_names()):
        print(f"  {view}")


if __name__ == "__main__":
    main()
