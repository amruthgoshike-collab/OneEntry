"""Business operations shared by the API routers and scripts/seed.py.

The routers own HTTP concerns and the Gemini calls that produce line items or
prose. Everything that touches the database — numbering, line item rows, GST
totals, PDF rendering, events, status transitions — lives here, so seeded data
carries exactly the same lineage as data created through the API: real
quotation numbers, `quotation_id` on every invoice, and an event trail on
every job.

`as_of` backdates what a call creates. The API never passes it; the seed script
always does.
"""
import logging
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app import models
from app.artifacts import artifact_path, company_context
from app.config import get_settings
from app.events import log_event
from app.money import (
    amount_in_words,
    compute_totals,
    hsn_summary,
    line_amount,
    q2,
)
from app.numbering import next_number
from app.pdf.render import render_pdf

logger = logging.getLogger(__name__)

DEFAULT_PAYMENT_TERMS = [
    "40% advance along with the work order.",
    "Balance on completion, payable within 7 days of invoice.",
]

# Columns carried verbatim from a quotation's line items to an invoice's.
COPIED_LINE_FIELDS = (
    "position",
    "description",
    "hsn_sac",
    "quantity",
    "unit",
    "rate",
    "tax_rate",
    "amount",
)


def _stamp(as_of: datetime | None) -> dict:
    """created_at override, or nothing so the server default fires."""
    return {"created_at": as_of} if as_of is not None else {}


def _on(as_of: datetime | None) -> date:
    return as_of.date() if as_of is not None else date.today()


def price_lines(lines: list[dict]) -> list[dict]:
    """Attach `amount` to each line. The single place amounts are computed.

    Callers supply description, hsn_sac, quantity, unit, rate and tax_rate;
    quantity x rate is worked out here so neither Gemini nor a seed fixture can
    hand us an amount that disagrees with its own quantity and rate.
    """
    priced = []
    for line in lines:
        line = dict(line)
        line["tax_rate"] = q2(line.get("tax_rate") if line.get("tax_rate") is not None else 18)
        line["amount"] = line_amount(line["quantity"], line["rate"])
        priced.append(line)
    return priced


def build_quotation(
    db: Session,
    job: models.Job,
    lines: list[dict],
    *,
    notes: str | None = None,
    payment_terms: list[str] | None = None,
    validity_days: int | None = None,
    as_of: datetime | None = None,
    render: bool = True,
) -> models.Quotation:
    """Persist a quotation and its line items, render the PDF, log events."""
    settings = get_settings()
    priced = price_lines(lines)
    totals = compute_totals(priced)
    validity_days = validity_days or settings.QUOTATION_VALIDITY_DAYS

    quotation = models.Quotation(
        job_id=job.id,
        quotation_number=next_number(db, models.Quotation.quotation_number, "QTN"),
        status="draft",
        notes=notes,
        subtotal=totals["subtotal"],
        gst_rate=totals["gst_rate"],
        gst_amount=totals["gst_amount"],
        total=totals["total"],
        **_stamp(as_of),
    )
    db.add(quotation)
    db.flush()

    for position, line in enumerate(priced):
        db.add(models.LineItem(quotation_id=quotation.id, position=position, **line))

    issued = _on(as_of)
    valid_until = issued + timedelta(days=validity_days)
    if render:
        pdf_path = artifact_path(quotation.quotation_number)
        try:
            render_pdf(
                "quotation.html",
                {
                    "company": company_context(),
                    "customer": job.customer,
                    "job": job,
                    "quotation": quotation,
                    "lines": priced,
                    "totals": totals,
                    "hsn_rows": hsn_summary(priced),
                    "amount_in_words": amount_in_words(totals["total"]),
                    "quotation_date": f"{issued:%d %b %Y}",
                    "valid_until": f"{valid_until:%d %b %Y}",
                    "payment_terms": payment_terms or DEFAULT_PAYMENT_TERMS,
                },
                pdf_path,
            )
            quotation.pdf_path = str(pdf_path)
        except Exception:
            # The numbers are the valuable part — keep them, retry the PDF later.
            logger.exception("PDF render failed for %s", quotation.quotation_number)

    log_event(
        db,
        job.id,
        "quotation_generated",
        f"{quotation.quotation_number} generated, {len(priced)} line items, "
        f"total {totals['total']}",
        at=as_of,
    )
    if job.status == "enquiry":
        previous, job.status = job.status, "quoted"
        log_event(db, job.id, "status_changed", f"{previous} -> {job.status}", at=as_of)

    return quotation


def build_invoice(
    db: Session,
    quotation: models.Quotation,
    *,
    as_of: datetime | None = None,
    render: bool = True,
) -> models.Invoice:
    """Approve a quotation and raise the invoice by copying its line items.

    No LLM anywhere in here — it copies rows that already exist, which is why
    approval returns in milliseconds.
    """
    settings = get_settings()
    job = quotation.job
    issued = _on(as_of)
    due_date = issued + timedelta(days=settings.INVOICE_DUE_DAYS)

    invoice = models.Invoice(
        job_id=job.id,
        quotation_id=quotation.id,
        invoice_number=next_number(db, models.Invoice.invoice_number, "INV"),
        status="unpaid",
        subtotal=quotation.subtotal,
        gst_rate=quotation.gst_rate,
        gst_amount=quotation.gst_amount,
        total=quotation.total,
        due_date=due_date,
        **_stamp(as_of),
    )
    db.add(invoice)
    db.flush()

    for source in quotation.line_items:
        db.add(
            models.LineItem(
                invoice_id=invoice.id,
                **{field: getattr(source, field) for field in COPIED_LINE_FIELDS},
            )
        )

    quotation.status = "approved"

    lines = [
        {field: getattr(source, field) for field in COPIED_LINE_FIELDS}
        for source in quotation.line_items
    ]
    totals = compute_totals(lines)

    if render:
        pdf_path = artifact_path(invoice.invoice_number)
        try:
            render_pdf(
                "invoice.html",
                {
                    "company": company_context(),
                    "customer": job.customer,
                    "job": job,
                    "quotation": quotation,
                    "invoice": invoice,
                    "lines": lines,
                    "totals": totals,
                    "hsn_rows": hsn_summary(lines),
                    "amount_in_words": amount_in_words(invoice.total),
                    "invoice_date": f"{issued:%d %b %Y}",
                    "due_date": f"{due_date:%d %b %Y}",
                },
                pdf_path,
            )
            invoice.pdf_path = str(pdf_path)
        except Exception:
            logger.exception("PDF render failed for %s", invoice.invoice_number)

    log_event(
        db,
        job.id,
        "quotation_approved",
        f"{quotation.quotation_number} approved by customer",
        at=as_of,
    )
    log_event(
        db,
        job.id,
        "invoice_created",
        f"{invoice.invoice_number} raised from {quotation.quotation_number}, "
        f"total {invoice.total}, due {due_date:%d %b %Y}",
        at=as_of,
    )
    if job.status != "approved":
        previous, job.status = job.status, "approved"
        log_event(db, job.id, "status_changed", f"{previous} -> {job.status}", at=as_of)

    return invoice


def build_certificate(
    db: Session,
    job: models.Job,
    scope_summary: str,
    *,
    as_of: datetime | None = None,
    render: bool = True,
) -> models.Certificate:
    """Persist a completion certificate and render it."""
    settings = get_settings()
    issued = _on(as_of)

    certificate = models.Certificate(
        job_id=job.id,
        certificate_number=next_number(
            db, models.Certificate.certificate_number, "CERT"
        ),
        scope_summary=scope_summary,
        issued_on=issued,
        **_stamp(as_of),
    )
    db.add(certificate)
    db.flush()

    if render:
        latest_invoice = max(job.invoices, key=lambda i: i.created_at, default=None)
        pdf_path = artifact_path(certificate.certificate_number)
        try:
            render_pdf(
                "certificate.html",
                {
                    "company": company_context(),
                    "customer": job.customer,
                    "job": job,
                    "certificate": certificate,
                    "invoice": latest_invoice,
                    "scope_summary": scope_summary,
                    "completion_date": (
                        f"{job.completed_on:%d %B %Y}" if job.completed_on else "—"
                    ),
                    "issue_date": f"{issued:%d %B %Y}",
                    "warranty_months": settings.WARRANTY_MONTHS,
                },
                pdf_path,
            )
            certificate.pdf_path = str(pdf_path)
        except Exception:
            logger.exception(
                "PDF render failed for %s", certificate.certificate_number
            )

    log_event(
        db,
        job.id,
        "certificate_issued",
        f"{certificate.certificate_number} issued to {job.customer.name}",
        at=as_of,
    )
    return certificate
