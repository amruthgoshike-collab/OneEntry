"""Quotation approval -> invoice.

There is deliberately no LLM call in this module. Approving copies rows that
already exist, which is why it returns in milliseconds while generating the
quotation takes ten seconds. That contrast is the product.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.db import get_db
from app.services import build_invoice

router = APIRouter(tags=["invoices"])


@router.post(
    "/quotations/{quotation_id}/approve", response_model=schemas.ApproveResponse
)
def approve_quotation(quotation_id: uuid.UUID, db: Session = Depends(get_db)):
    quotation = db.execute(
        select(models.Quotation)
        .where(models.Quotation.id == quotation_id)
        .options(
            selectinload(models.Quotation.line_items),
            selectinload(models.Quotation.job).selectinload(models.Job.customer),
        )
    ).scalar_one_or_none()
    if quotation is None:
        raise HTTPException(status_code=404, detail=f"Quotation {quotation_id} not found")
    if quotation.status == "approved":
        # Approving twice would mint a second invoice for the same work.
        raise HTTPException(
            status_code=409,
            detail=f"{quotation.quotation_number} is already approved",
        )

    invoice = build_invoice(db, quotation)
    db.commit()

    return {
        "quotation": db.execute(
            select(models.Quotation)
            .where(models.Quotation.id == quotation.id)
            .options(selectinload(models.Quotation.line_items))
        ).scalar_one(),
        "invoice": db.execute(
            select(models.Invoice)
            .where(models.Invoice.id == invoice.id)
            .options(selectinload(models.Invoice.line_items))
        ).scalar_one(),
    }


@router.get("/invoices", response_model=schemas.InvoiceList)
def list_invoices(db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.Invoice)
        .join(models.Job, models.Job.id == models.Invoice.job_id)
        .join(models.Entity, models.Entity.id == models.Job.customer_id)
        .options(
            selectinload(models.Invoice.quotation),
            selectinload(models.Invoice.job).selectinload(models.Job.customer),
        )
        .order_by(models.Invoice.created_at.desc())
    ).scalars().all()

    return {
        "items": [
            schemas.InvoiceSummary(
                id=inv.id,
                job_id=inv.job_id,
                invoice_number=inv.invoice_number,
                quotation_number=inv.quotation.quotation_number if inv.quotation else None,
                status=inv.status,
                total=inv.total,
                due_date=inv.due_date,
                created_at=inv.created_at,
                job_number=inv.job.job_number,
                job_title=inv.job.title,
                customer_name=inv.job.customer.name,
                pdf_path=inv.pdf_path,
            )
            for inv in rows
        ]
    }


@router.get("/invoices/{invoice_id}/pdf")
def get_invoice_pdf(invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    invoice = db.get(models.Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    if not invoice.pdf_path or not Path(invoice.pdf_path).exists():
        raise HTTPException(
            status_code=404,
            detail=f"No PDF has been rendered for {invoice.invoice_number}",
        )
    return FileResponse(
        invoice.pdf_path,
        media_type="application/pdf",
        filename=f"{invoice.invoice_number}.pdf",
    )
