"""The two-path search router.

Structured (text-to-SQL over `v_search`) answers anything with a filter in it:
numbers, comparisons, dates, statuses, aggregations. Semantic (Chroma) answers
descriptive recall — "that painting job" — where there is nothing to filter on.

Pure vector search cannot answer "above 20000", so numbers never go to Chroma.
The tie-break is deliberate: **any** structured signal wins, and only a query
with no filterable content at all falls through to semantic.
"""
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.llm.client import GeminiError, generate_json
from app.llm.prompts import SEARCH_ANSWER_PROMPT
from app.models import Document, Job
from app.search import chroma
from app.search.sql import UnsafeSQL, generate_sql, run_sql

logger = logging.getLogger(__name__)

SEMANTIC_RESULTS = 5
ANSWER_ROW_SAMPLE = 20

# Any of these means the question has something SQL can filter or aggregate on.
_COMPARISON = r"above|below|over|under|more than|less than|greater|at least|at most|between|highest|lowest|cheaper|costlier|>|<"
_AGGREGATION = r"how many|how much|count|total|sum|average|avg|most|least|top|biggest|largest|smallest|worth|value of|which customer|who gave"
_STATUS = r"unpaid|paid|pending|overdue|outstanding|draft|approved|completed|quoted|in progress|issued|extracted|failed|enquiry"
_DATES = (
    r"last month|this month|last week|this week|last year|this year|yesterday|today|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec|"
    r"since|before|after|between|q1|q2|q3|q4|financial year|fy"
)

_SIGNALS = (
    ("number", re.compile(r"\d")),
    ("comparison", re.compile(_COMPARISON, re.IGNORECASE)),
    ("aggregation", re.compile(_AGGREGATION, re.IGNORECASE)),
    ("status filter", re.compile(_STATUS, re.IGNORECASE)),
    ("date", re.compile(_DATES, re.IGNORECASE)),
)


@dataclass
class SearchResult:
    mode: str
    answer: str
    results: list[dict]
    sql: str | None = None
    reason: str = ""


def choose_mode(question: str) -> tuple[str, str]:
    """Pick a path and say why. Returns (mode, reason)."""
    for name, pattern in _SIGNALS:
        match = pattern.search(question)
        if match:
            return "structured", f"{name} in query ({match.group(0)!r})"
    return "semantic", "no filterable signal; descriptive recall"


# --- shared helpers ----------------------------------------------------------

def _jsonable(value):
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _clean_rows(rows: list[dict]) -> list[dict]:
    return [{key: _jsonable(value) for key, value in row.items()} for row in rows]


def _write_answer(question: str, rows: list[dict]) -> str:
    """One natural-language sentence over the rows we actually got back."""
    sample = json.dumps(rows[:ANSWER_ROW_SAMPLE], indent=2, default=str)
    try:
        result = generate_json(
            SEARCH_ANSWER_PROMPT.format(
                question=question, row_count=len(rows), rows=sample
            )
        )
        answer = str(result.get("answer") or "").strip()
        if answer:
            return answer
    except GeminiError:
        logger.exception("Answer generation failed; falling back to a plain count")
    return f"{len(rows)} matching record(s)." if rows else "Nothing matched that."


# --- path A: structured ------------------------------------------------------

def run_structured(db: Session, question: str) -> SearchResult:
    sql = generate_sql(question)
    rows = _clean_rows(run_sql(db, sql))
    return SearchResult(
        mode="structured",
        answer=_write_answer(question, rows),
        results=rows,
        sql=sql,
    )


# --- path B: semantic --------------------------------------------------------

def _hydrate(db: Session, ids: list[str]) -> list[dict]:
    """Chroma returns ids and metadata; the record itself comes from Postgres."""
    keys = []
    for raw in ids:
        try:
            keys.append(uuid.UUID(raw))
        except ValueError:
            logger.warning("Chroma returned a non-UUID id: %r", raw)

    jobs = {
        job.id: job
        for job in db.execute(
            select(Job)
            .where(Job.id.in_(keys))
            .options(
                selectinload(Job.customer),
                selectinload(Job.invoices),
                selectinload(Job.quotations),
            )
        ).scalars()
    }
    documents = {
        doc.id: doc
        for doc in db.execute(
            select(Document)
            .where(Document.id.in_(keys))
            .options(selectinload(Document.job))
        ).scalars()
    }

    rows = []
    for key in keys:  # preserve Chroma's ranking
        if key in jobs:
            job = jobs[key]
            latest = max(
                list(job.invoices) + list(job.quotations),
                key=lambda row: row.created_at,
                default=None,
            )
            rows.append({
                "record_type": "job",
                "id": str(job.id),
                "number": job.job_number,
                "party_name": job.customer.name if job.customer else None,
                "amount": f"{latest.total:.2f}" if latest else None,
                "status": job.status,
                "record_date": _jsonable(job.created_at),
                "job_id": str(job.id),
                "job_title": job.title,
            })
        elif key in documents:
            doc = documents[key]
            rows.append({
                "record_type": "document",
                "id": str(doc.id),
                "number": doc.filename,
                "party_name": doc.vendor_name,
                "amount": f"{doc.total_amount:.2f}" if doc.total_amount else None,
                "status": doc.status,
                "record_date": _jsonable(doc.document_date or doc.created_at),
                "job_id": str(doc.job_id) if doc.job_id else None,
                "job_title": doc.job.title if doc.job else None,
            })
        else:
            # Indexed but since deleted — Chroma is derived, so this is drift.
            logger.info("Chroma hit %s has no row in Postgres; skipping", key)
    return rows


def run_semantic(db: Session, question: str) -> SearchResult:
    hits = chroma.query(question, n_results=SEMANTIC_RESULTS)
    ids = hits["ids"][0] if hits.get("ids") else []
    rows = _hydrate(db, ids)
    return SearchResult(
        mode="semantic",
        answer=_write_answer(question, rows),
        results=rows,
    )


# --- entry point -------------------------------------------------------------

def search(db: Session, question: str) -> SearchResult:
    """Route the question, run that path, fall back when structured fails."""
    mode, reason = choose_mode(question)
    logger.info("search %r -> %s (%s)", question, mode, reason)

    if mode == "structured":
        try:
            result = run_structured(db, question)
            result.reason = reason
            return result
        except (UnsafeSQL, GeminiError, SQLAlchemyError) as exc:
            # A rejected or un-executable SELECT shouldn't be a dead end —
            # semantic may still answer, and an answer beats a 502.
            logger.warning("Structured path failed (%s); trying semantic", exc)
            result = run_semantic(db, question)
            result.reason = f"{reason}; structured failed ({exc}), fell back"
            return result

    result = run_semantic(db, question)
    result.reason = reason
    return result
