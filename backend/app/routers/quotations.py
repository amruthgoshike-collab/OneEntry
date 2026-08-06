import logging
import uuid
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.config import STORAGE_ROOT, get_settings
from app.db import get_db
from app.events import log_event
from app.llm.client import GeminiError, generate_json
from app.llm.prompts import QUOTATION_PROMPT
from app.money import amount_in_words, compute_totals, hsn_summary, line_amount, parse_decimal, q2
from app.numbering import next_number
from app.pdf.render import render_pdf

logger = logging.getLogger(__name__)
router = APIRouter(tags=["quotations"])

DEFAULT_PAYMENT_TERMS = [
    "40% advance along with the work order.",
    "Balance on completion, payable within 7 days of invoice.",
]


def _price_lines(raw_items: list[dict]) -> list[dict]:
    """Turn Gemini's line items into priced lines.

    Gemini supplies only description, code, quantity, unit and rate — every
    amount below is computed here, never taken from the model.
    """
    lines = []
    for item in raw_items:
        description = (item.get("description") or "").strip()
        quantity = parse_decimal(item.get("quantity"))
        rate = parse_decimal(item.get("rate"))
        if not description or quantity is None or rate is None:
            logger.warning("Dropping unusable line item from Gemini: %r", item)
            continue

        tax_rate = parse_decimal(item.get("tax_rate"))
        hsn_sac = (item.get("hsn_sac") or "").strip() or None
        lines.append({
            "description": description,
            "hsn_sac": hsn_sac[:10] if hsn_sac else None,
            "quantity": quantity,
            "unit": (item.get("unit") or "").strip()[:20] or None,
            "rate": rate,
            "tax_rate": q2(tax_rate) if tax_rate is not None else q2(18),
            "amount": line_amount(quantity, rate),
        })
    return lines


def _company() -> dict:
    settings = get_settings()
    return {
        "name": settings.COMPANY_NAME,
        "address": settings.COMPANY_ADDRESS,
        "gstin": settings.COMPANY_GSTIN,
        "state": settings.COMPANY_STATE,
        "phone": settings.COMPANY_PHONE,
        "email": settings.COMPANY_EMAIL,
    }


def _artifact_path(number: str) -> Path:
    today = date.today()
    return STORAGE_ROOT / "generated" / f"{today:%Y}" / f"{today:%m}" / f"{number}.pdf"


@router.post(
    "/jobs/{job_id}/quotation", response_model=schemas.Quotation, status_code=201
)
def create_quotation(
    job_id: uuid.UUID,
    payload: schemas.QuotationCreate | None = None,
    db: Session = Depends(get_db),
):
    job = db.execute(
        select(models.Job)
        .where(models.Job.id == job_id)
        .options(selectinload(models.Job.customer))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    extra_notes = ""
    if payload and payload.notes:
        extra_notes = f"\nExtra instructions from the contractor: {payload.notes}"

    prompt = QUOTATION_PROMPT.format(
        job_number=job.job_number,
        title=job.title,
        description=job.description or "(no description given)",
        site_address=job.site_address or "(not stated)",
        customer_name=job.customer.name,
        extra_notes=extra_notes,
    )

    try:
        result = generate_json(prompt)
    except GeminiError as exc:
        raise HTTPException(status_code=502, detail=f"Quotation generation failed: {exc}")

    lines = _price_lines(result.get("line_items") or [])
    if not lines:
        raise HTTPException(
            status_code=502,
            detail="Gemini returned no usable line items for this job description",
        )

    totals = compute_totals(lines)
    settings = get_settings()
    validity_days = result.get("validity_days")
    validity_days = (
        int(validity_days)
        if isinstance(validity_days, int) or str(validity_days or "").isdigit()
        else settings.QUOTATION_VALIDITY_DAYS
    )

    quotation = models.Quotation(
        job_id=job.id,
        quotation_number=next_number(db, models.Quotation.quotation_number, "QTN"),
        status="draft",
        notes=(payload.notes if payload else None) or result.get("notes"),
        subtotal=totals["subtotal"],
        gst_rate=totals["gst_rate"],
        gst_amount=totals["gst_amount"],
        total=totals["total"],
    )
    db.add(quotation)
    db.flush()

    for position, line in enumerate(lines):
        db.add(models.LineItem(quotation_id=quotation.id, position=position, **line))

    payment_terms = [
        str(term) for term in (result.get("payment_terms") or []) if str(term).strip()
    ] or DEFAULT_PAYMENT_TERMS
    valid_until = date.today() + timedelta(days=validity_days)

    pdf_path = _artifact_path(quotation.quotation_number)
    try:
        render_pdf(
            "quotation.html",
            {
                "company": _company(),
                "customer": job.customer,
                "job": job,
                "quotation": quotation,
                "lines": lines,
                "totals": totals,
                "hsn_rows": hsn_summary(lines),
                "amount_in_words": amount_in_words(totals["total"]),
                "quotation_date": f"{date.today():%d %b %Y}",
                "valid_until": f"{valid_until:%d %b %Y}",
                "payment_terms": payment_terms,
            },
            pdf_path,
        )
        quotation.pdf_path = str(pdf_path)
    except Exception:
        # The numbers are the valuable part — keep them and let the PDF be retried.
        logger.exception("PDF render failed for %s", quotation.quotation_number)

    log_event(
        db,
        job.id,
        "quotation_generated",
        f"{quotation.quotation_number} generated, {len(lines)} line items, "
        f"total {totals['total']}",
    )
    if job.status == "enquiry":
        previous, job.status = job.status, "quoted"
        log_event(db, job.id, "status_changed", f"{previous} -> {job.status}")

    db.commit()

    return db.execute(
        select(models.Quotation)
        .where(models.Quotation.id == quotation.id)
        .options(selectinload(models.Quotation.line_items))
    ).scalar_one()


@router.get("/quotations/{quotation_id}/pdf")
def get_quotation_pdf(quotation_id: uuid.UUID, db: Session = Depends(get_db)):
    quotation = db.get(models.Quotation, quotation_id)
    if quotation is None:
        raise HTTPException(status_code=404, detail=f"Quotation {quotation_id} not found")
    if not quotation.pdf_path or not Path(quotation.pdf_path).exists():
        raise HTTPException(
            status_code=404,
            detail=f"No PDF has been rendered for {quotation.quotation_number}",
        )
    return FileResponse(
        quotation.pdf_path,
        media_type="application/pdf",
        filename=f"{quotation.quotation_number}.pdf",
    )
