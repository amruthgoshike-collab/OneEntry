import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.db import get_db
from app.llm.client import GeminiError, generate_json
from app.llm.prompts import CERTIFICATE_PROMPT
from app.money import format_inr
from app.services import build_certificate

router = APIRouter(tags=["certificates"])

_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def _as_paragraph(text: str) -> str:
    """Flatten whatever Gemini returned into one paragraph.

    The prompt forbids bullets and line breaks; this enforces it rather than
    trusting it, since the certificate reads as a formal statement.
    """
    lines = (_BULLET_RE.sub("", line).strip() for line in text.splitlines())
    return re.sub(r"\s{2,}", " ", " ".join(line for line in lines if line)).strip()


def _scope_lines(job: models.Job) -> list[models.LineItem]:
    """What was actually billed, preferring invoices over quotations.

    A job normally has one invoice. If it has several, identical descriptions
    are collapsed — the certificate describes scope, not billing detail.
    """
    sources = [inv.line_items for inv in job.invoices] or [
        q.line_items for q in job.quotations
    ]
    seen, lines = set(), []
    for group in sources:
        for item in group:
            key = (item.description or "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                lines.append(item)
    return lines


def _format_lines(lines: list[models.LineItem]) -> str:
    if not lines:
        return "  (nothing itemised — rely on the job description)"
    return "\n".join(
        f"  - {item.description}: {format_inr(item.quantity)} "
        f"{item.unit or 'unit'} at {format_inr(item.rate)} per {item.unit or 'unit'}"
        for item in lines
    )


@router.post(
    "/jobs/{job_id}/certificate", response_model=schemas.Certificate, status_code=201
)
def create_certificate(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.execute(
        select(models.Job)
        .where(models.Job.id == job_id)
        .options(
            selectinload(models.Job.customer),
            selectinload(models.Job.invoices).selectinload(models.Invoice.line_items),
            selectinload(models.Job.quotations).selectinload(
                models.Quotation.line_items
            ),
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if job.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=(
                f"{job.job_number} is {job.status}, not completed. "
                "Mark the job completed before issuing a completion certificate."
            ),
        )

    lines = _scope_lines(job)
    prompt = CERTIFICATE_PROMPT.format(
        job_number=job.job_number,
        title=job.title,
        description=job.description or "(no description given)",
        site_address=job.site_address or "(not stated)",
        customer_name=job.customer.name,
        completed_on=f"{job.completed_on:%d %b %Y}" if job.completed_on else "(not recorded)",
        line_items=_format_lines(lines),
    )

    try:
        result = generate_json(prompt)
    except GeminiError as exc:
        raise HTTPException(
            status_code=502, detail=f"Certificate generation failed: {exc}"
        )

    scope_summary = _as_paragraph(str(result.get("scope_summary") or ""))
    if not scope_summary:
        raise HTTPException(
            status_code=502, detail="Gemini returned an empty scope summary"
        )

    certificate = build_certificate(db, job, scope_summary)
    db.commit()
    db.refresh(certificate)
    return certificate


@router.get("/certificates/{certificate_id}/pdf")
def get_certificate_pdf(certificate_id: uuid.UUID, db: Session = Depends(get_db)):
    certificate = db.get(models.Certificate, certificate_id)
    if certificate is None:
        raise HTTPException(
            status_code=404, detail=f"Certificate {certificate_id} not found"
        )
    if not certificate.pdf_path or not Path(certificate.pdf_path).exists():
        raise HTTPException(
            status_code=404,
            detail=f"No PDF has been rendered for {certificate.certificate_number}",
        )
    return FileResponse(
        certificate.pdf_path,
        media_type="application/pdf",
        filename=f"{certificate.certificate_number}.pdf",
    )
