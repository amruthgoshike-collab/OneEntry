import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.db import get_db
from app.llm.client import GeminiError, generate_json
from app.llm.prompts import QUOTATION_PROMPT
from app.money import parse_decimal
from app.services import build_quotation

logger = logging.getLogger(__name__)
router = APIRouter(tags=["quotations"])


def _parse_lines(raw_items: list[dict]) -> list[dict]:
    """Coerce Gemini's line items into the shape the service expects.

    Note what is absent: no amount. Gemini supplies only quantity and rate,
    and `services.price_lines` works out every amount in Python.
    """
    lines = []
    for item in raw_items:
        description = (item.get("description") or "").strip()
        quantity = parse_decimal(item.get("quantity"))
        rate = parse_decimal(item.get("rate"))
        if not description or quantity is None or rate is None:
            logger.warning("Dropping unusable line item from Gemini: %r", item)
            continue

        hsn_sac = (item.get("hsn_sac") or "").strip() or None
        lines.append({
            "description": description,
            "hsn_sac": hsn_sac[:10] if hsn_sac else None,
            "quantity": quantity,
            "unit": (item.get("unit") or "").strip()[:20] or None,
            "rate": rate,
            "tax_rate": parse_decimal(item.get("tax_rate")),
        })
    return lines


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

    lines = _parse_lines(result.get("line_items") or [])
    if not lines:
        raise HTTPException(
            status_code=502,
            detail="Gemini returned no usable line items for this job description",
        )

    raw_validity = result.get("validity_days")
    validity_days = (
        int(raw_validity)
        if isinstance(raw_validity, int) or str(raw_validity or "").isdigit()
        else None
    )
    payment_terms = [
        str(term) for term in (result.get("payment_terms") or []) if str(term).strip()
    ]

    quotation = build_quotation(
        db,
        job,
        lines,
        notes=(payload.notes if payload else None) or result.get("notes"),
        payment_terms=payment_terms or None,
        validity_days=validity_days,
    )
    db.commit()

    return db.execute(
        select(models.Quotation)
        .where(models.Quotation.id == quotation.id)
        .options(selectinload(models.Quotation.line_items))
    ).scalar_one()


@router.get("/quotations", response_model=schemas.QuotationList)
def list_quotations(db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.Quotation)
        .join(models.Job, models.Job.id == models.Quotation.job_id)
        .join(models.Entity, models.Entity.id == models.Job.customer_id)
        .options(
            selectinload(models.Quotation.line_items),
            selectinload(models.Quotation.job).selectinload(models.Job.customer),
        )
        .order_by(models.Quotation.created_at.desc())
    ).scalars().all()

    return {
        "items": [
            schemas.QuotationSummary(
                id=q.id,
                job_id=q.job_id,
                quotation_number=q.quotation_number,
                status=q.status,
                total=q.total,
                created_at=q.created_at,
                job_number=q.job.job_number,
                job_title=q.job.title,
                customer_name=q.job.customer.name,
                line_item_count=len(q.line_items),
                pdf_path=q.pdf_path,
            )
            for q in rows
        ]
    }


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
