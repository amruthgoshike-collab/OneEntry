"""Extraction smoke test.

Runs the real Gemini extraction over every readable file in samples/ and prints
what came back. Needs GEMINI_API_KEY; needs no database and no running server.

    cd backend && python -m tests.test_extract
"""
import sys
import time
from pathlib import Path

from app.config import BACKEND_DIR
from app.extraction import extract_from_bytes, guess_mime_type
from app.llm.client import SUPPORTED_MIME_TYPES

SAMPLES_DIR = BACKEND_DIR.parent / "samples"

DETAIL_FIELDS = (
    "doc_type",
    "vendor_name",
    "document_date",
    "due_date",
    "total_amount",
    "expense_category",
    "summary",
)


def _truncate(value, width: int) -> str:
    text = "-" if value in (None, "") else str(value)
    return text if len(text) <= width else text[: width - 1] + "…"


def _print_table(rows: list[dict]) -> None:
    headers = ("file", "doc_type", "vendor_name", "document_date", "total_amount", "expense_category")
    caps = (26, 16, 26, 12, 12, 16)
    widths = [
        min(cap, max(len(h), *(len(str(r.get(h) or "-")) for r in rows)))
        for h, cap in zip(headers, caps)
    ]

    line = "  ".join(h.upper().ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(_truncate(row.get(h), w).ljust(w) for h, w in zip(headers, widths)))


def main() -> int:
    if not SAMPLES_DIR.exists():
        print(f"No samples directory at {SAMPLES_DIR}")
        return 1

    files = [
        path
        for path in sorted(SAMPLES_DIR.rglob("*"))
        if path.is_file() and guess_mime_type(path.name) in SUPPORTED_MIME_TYPES
    ]
    if not files:
        print(f"No PDFs or images in {SAMPLES_DIR} — drop some real bills in there.")
        return 1

    print(f"Extracting {len(files)} file(s) from {SAMPLES_DIR}\n")
    rows, failures = [], 0

    for path in files:
        mime_type = guess_mime_type(path.name)
        size_kb = path.stat().st_size / 1024
        print("=" * 78)
        print(f"{path.name}   ({mime_type}, {size_kb:.1f} KB)")
        print("-" * 78)

        started = time.perf_counter()
        try:
            fields = extract_from_bytes(path.read_bytes(), mime_type, path.name)
        except Exception as exc:
            failures += 1
            print(f"  FAILED  {type(exc).__name__}: {exc}\n")
            rows.append({"file": path.name, "doc_type": "FAILED"})
            continue
        elapsed = time.perf_counter() - started

        for field in DETAIL_FIELDS:
            value = fields.get(field)
            print(f"  {field:<18}{'-' if value in (None, '') else value}")

        extra = fields.get("extracted_json") or {}
        line_items = extra.get("line_items") or []
        print(f"  {'line_items':<18}{len(line_items)} row(s)")
        for item in line_items:
            print(
                f"      - {_truncate(item.get('description'), 38):<38}"
                f"{str(item.get('quantity') or '-'):>8} {str(item.get('unit') or ''):<6}"
                f"@ {str(item.get('rate') or '-'):>10} = {str(item.get('amount') or '-'):>12}"
            )
        for field in ("document_number", "vendor_gstin", "subtotal", "tax_amount", "notes"):
            if extra.get(field):
                print(f"  {field:<18}{extra[field]}")
        print(f"  {'elapsed':<18}{elapsed:.1f}s\n")

        rows.append({"file": path.name, **{k: fields.get(k) for k in DETAIL_FIELDS}})

    print("=" * 78)
    print(f"SUMMARY  ({len(files) - failures}/{len(files)} extracted)\n")
    _print_table(rows)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
