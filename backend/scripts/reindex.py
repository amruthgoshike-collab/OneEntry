"""Rebuild the Chroma collection from Postgres.

Postgres is the source of truth; the index is derived. Run this after a bulk
import, after changing what gets embedded, or any time the two have drifted.
The collection is dropped and rebuilt rather than patched, so it always ends
up matching the database exactly.

    cd backend && python -m scripts.reindex
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import SessionLocal
from app.models import Document, Job
from app.search import chroma

BATCH = 100


def _flush(collection, batch: list[tuple[str, str, dict]]) -> int:
    if not batch:
        return 0
    collection.upsert(
        ids=[row[0] for row in batch],
        documents=[row[1] for row in batch],
        metadatas=[row[2] for row in batch],
    )
    return len(batch)


def main() -> int:
    print(f"Chroma path: {chroma.chroma_dir()}")

    chroma.reset_collection()
    collection = chroma.get_collection()

    indexed = {"job": 0, "document": 0}
    skipped = {"job": 0, "document": 0}
    batch: list[tuple[str, str, dict]] = []

    with SessionLocal() as db:
        jobs = db.execute(
            select(Job).options(
                selectinload(Job.customer),
                selectinload(Job.invoices),
                selectinload(Job.quotations),
            )
        ).scalars().all()
        for job in jobs:
            text = chroma.job_text(job)
            if not text:
                skipped["job"] += 1
                continue
            batch.append((str(job.id), text, chroma.job_metadata(job)))
            indexed["job"] += 1
            if len(batch) >= BATCH:
                _flush(collection, batch)
                batch = []

        documents = db.execute(
            select(Document)
            .where(Document.status == "extracted")
            .options(selectinload(Document.job).selectinload(Job.customer))
        ).scalars().all()
        for document in documents:
            text = chroma.document_text(document)
            if not text:
                skipped["document"] += 1
                continue
            batch.append((str(document.id), text, chroma.document_metadata(document)))
            indexed["document"] += 1
            if len(batch) >= BATCH:
                _flush(collection, batch)
                batch = []

        _flush(collection, batch)

    total = collection.count()
    print(
        f"\nIndexed {indexed['job']} job(s) and {indexed['document']} document(s)."
    )
    if any(skipped.values()):
        print(
            f"Skipped {skipped['job']} job(s) and {skipped['document']} document(s) "
            "with nothing to embed."
        )
    print(f"Collection '{chroma.COLLECTION_NAME}' now holds {total} record(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
