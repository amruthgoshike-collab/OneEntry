"""Document bytes -> normalized field values.

Kept free of FastAPI and the DB session so the smoke test in
`tests/test_extract.py` can run it over samples/ without a server or database.
"""
import mimetypes
from datetime import date, datetime
from decimal import Decimal

from app.llm.client import SUPPORTED_MIME_TYPES, generate_json
from app.llm.prompts import DOC_TYPES, DOCUMENT_EXTRACTION_PROMPT, EXPENSE_CATEGORIES
from app.money import parse_decimal

_NULLISH = {"", "n/a", "na", "none", "null", "-", "not stated", "not available"}

# Indian bills are as likely to be dd/mm/yyyy as ISO.
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y")


def guess_mime_type(filename: str, fallback: str | None = None) -> str | None:
    """Best-effort content type for an uploaded or on-disk file."""
    if fallback and fallback in SUPPORTED_MIME_TYPES:
        return fallback
    guessed, _ = mimetypes.guess_type(filename)
    if guessed == "image/jpg":  # some platforms report this
        return "image/jpeg"
    return guessed


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in _NULLISH else text


def to_decimal(value) -> Decimal | None:
    """'Rs. 1,84,500.00' -> Decimal('184500.00'). None when not a number."""
    return parse_decimal(value)


def to_date(value) -> date | None:
    text = _clean(value)
    if text is None:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _one_of(value, allowed: tuple[str, ...], default: str) -> str:
    text = _clean(value)
    if text is None:
        return default
    normalized = text.lower().replace(" ", "_").replace("-", "_")
    return normalized if normalized in allowed else default


def normalize(raw: dict) -> dict:
    """Map Gemini's JSON onto Document column values.

    The full model output is kept in extracted_json so nothing is lost when the
    prompt returns more than the columns hold.
    """
    return {
        "doc_type": _one_of(raw.get("doc_type"), DOC_TYPES, "other"),
        "vendor_name": _clean(raw.get("vendor_name")),
        "total_amount": to_decimal(raw.get("total_amount")),
        "document_date": to_date(raw.get("document_date")),
        "due_date": to_date(raw.get("due_date")),
        "expense_category": _one_of(
            raw.get("expense_category"), EXPENSE_CATEGORIES, "other"
        ),
        "summary": _clean(raw.get("summary")),
        "extracted_json": raw,
    }


def extract_from_bytes(file_bytes: bytes, mime_type: str, filename: str = "") -> dict:
    """Send a document to Gemini and return normalized Document field values."""
    raw = generate_json(
        DOCUMENT_EXTRACTION_PROMPT,
        file_bytes=file_bytes,
        mime_type=mime_type,
    )
    return normalize(raw)
