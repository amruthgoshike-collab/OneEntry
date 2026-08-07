"""ChromaDB semantic index over jobs and extracted documents.

**Chroma is never the source of truth — Postgres is.** Every write from a
request path is best-effort: failures are logged and swallowed so an indexing
problem can never fail a job creation or a document upload. When the two drift,
`scripts/reindex.py` rebuilds the collection from Postgres.

This half of search handles fuzzy recall ("that painting quotation from
January"). Numeric and filtered questions go to text-to-SQL against `v_search`
instead — pure vector search cannot answer "above 20000".
"""
import logging
import threading
from datetime import date, datetime
from pathlib import Path

from app.config import BACKEND_DIR, get_settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "oneentry"
# all-MiniLM-L6-v2, run through ONNX — Chroma's default, so no torch needed.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_collection = None
_lock = threading.Lock()


def chroma_dir() -> Path:
    """CHROMA_PATH, resolved against the repo root when it is relative."""
    raw = Path(get_settings().CHROMA_PATH)
    return raw if raw.is_absolute() else (BACKEND_DIR.parent / raw).resolve()


def _client():
    import chromadb
    from chromadb.config import Settings

    return chromadb.PersistentClient(
        path=str(chroma_dir()),
        settings=Settings(anonymized_telemetry=False),
    )


def get_collection():
    """The one collection, created on first use. Raises if Chroma is broken."""
    global _collection
    if _collection is not None:
        return _collection
    with _lock:
        if _collection is None:
            from chromadb.utils import embedding_functions

            _collection = _client().get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_functions.DefaultEmbeddingFunction(),
                # Sentence embeddings compare by angle, not magnitude.
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                "Chroma collection '%s' ready at %s (%d records)",
                COLLECTION_NAME,
                chroma_dir(),
                _collection.count(),
            )
    return _collection


def reset_collection() -> None:
    """Drop the collection so the next get_collection() builds it fresh.

    Rebuilding beats patching: rows deleted from Postgres would otherwise
    linger in the index as vectors nothing points at.
    """
    global _collection
    with _lock:
        try:
            _client().delete_collection(COLLECTION_NAME)
            logger.info("Dropped Chroma collection '%s'", COLLECTION_NAME)
        except Exception:
            logger.info("No existing '%s' collection to drop", COLLECTION_NAME)
        _collection = None


def warm_up() -> None:
    """Load the embedding model off the request path, tolerating failure."""

    def _load():
        try:
            get_collection()
        except Exception:
            logger.exception("Chroma warm-up failed; search will retry on demand")

    threading.Thread(target=_load, name="chroma-warmup", daemon=True).start()


# --- what gets embedded ------------------------------------------------------

def _joined(*parts) -> str:
    return " ".join(str(p).strip() for p in parts if p and str(p).strip())


def _iso(value) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return ""


def job_text(job) -> str:
    """Title, description and customer name."""
    customer = getattr(job, "customer", None)
    return _joined(job.title, job.description, customer.name if customer else None)


def document_text(document) -> str:
    """The one-line summary plus the vendor."""
    return _joined(document.summary, document.vendor_name)


def _job_amount(job) -> float:
    """Latest invoice total, else latest quotation total, else zero.

    A brand new job has neither, and 0.0 is the honest answer at that point;
    a later update or a reindex fills it in.
    """
    for collection in (getattr(job, "invoices", None), getattr(job, "quotations", None)):
        if collection:
            latest = max(collection, key=lambda row: row.created_at)
            return float(latest.total or 0)
    return 0.0


def job_metadata(job) -> dict:
    customer = getattr(job, "customer", None)
    return {
        "record_type": "job",
        "job_id": str(job.id),
        "customer_name": customer.name if customer else "",
        "vendor_name": "",
        "date": _iso(job.created_at),
        "amount": _job_amount(job),
        "number": job.job_number or "",
    }


def document_metadata(document) -> dict:
    job = getattr(document, "job", None)
    customer = getattr(job, "customer", None) if job else None
    return {
        "record_type": "document",
        "job_id": str(document.job_id) if document.job_id else "",
        "customer_name": customer.name if customer else "",
        "vendor_name": document.vendor_name or "",
        "date": _iso(document.document_date or document.created_at),
        "amount": float(document.total_amount or 0),
        "number": document.filename or "",
    }


# --- writes ------------------------------------------------------------------

def upsert(record_id: str, text: str, metadata: dict) -> None:
    """Raw upsert. Raises — callers on a request path must use index_*."""
    get_collection().upsert(ids=[record_id], documents=[text], metadatas=[metadata])


def index_job(job) -> bool:
    """Best-effort. Returns whether the job made it into the index."""
    try:
        text = job_text(job)
        if not text:
            return False
        upsert(str(job.id), text, job_metadata(job))
        return True
    except Exception:
        logger.exception("Chroma indexing failed for job %s (continuing)", job.id)
        return False


def index_document(document) -> bool:
    """Best-effort. Only extracted documents carry anything worth embedding."""
    try:
        if document.status != "extracted":
            return False
        text = document_text(document)
        if not text:
            logger.info(
                "Document %s has no summary or vendor to embed; skipping index",
                document.id,
            )
            return False
        upsert(str(document.id), text, document_metadata(document))
        return True
    except Exception:
        logger.exception(
            "Chroma indexing failed for document %s (continuing)", document.id
        )
        return False


# --- reads -------------------------------------------------------------------

def query(text: str, n_results: int = 5, where: dict | None = None) -> dict:
    """Raw similarity query. Returns Chroma's response verbatim."""
    return get_collection().query(
        query_texts=[text],
        n_results=n_results,
        where=where or None,
    )
