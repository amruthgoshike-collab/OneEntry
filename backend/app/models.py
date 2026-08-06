"""SQLAlchemy models — SOURCE OF TRUTH for the schema.

NOTE: this file was reconstructed from api_contract.md (the scaffold commit
claimed a schema but never committed one). Review before building routers.

`jobs` is the spine: quotations, invoices, certificates, documents, and
events all carry job_id. Money is Numeric(12, 2), never float.
"""
import uuid

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Entity(Base):
    """Customers and vendors."""

    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # customer | vendor
    gstin: Mapped[str | None] = mapped_column(String(15))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    jobs: Mapped[list["Job"]] = relationship(back_populates="customer")


class Job(Base):
    """The spine. Every downstream artifact hangs off a job."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    job_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # JOB-0001
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    site_address: Mapped[str | None] = mapped_column(Text)
    # enquiry | quoted | approved | in_progress | completed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="enquiry")
    completed_on: Mapped[str | None] = mapped_column(Date)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    customer: Mapped["Entity"] = relationship(back_populates="jobs")
    quotations: Mapped[list["Quotation"]] = relationship(back_populates="job")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="job")
    certificates: Mapped[list["Certificate"]] = relationship(back_populates="job")
    documents: Mapped[list["Document"]] = relationship(back_populates="job")
    events: Mapped[list["JobEvent"]] = relationship(
        back_populates="job", order_by="JobEvent.created_at"
    )


class Quotation(Base):
    __tablename__ = "quotations"

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    quotation_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # QTN-0001
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # draft | approved
    notes: Mapped[str | None] = mapped_column(Text)
    subtotal: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    gst_rate: Mapped[object] = mapped_column(Numeric(5, 2), nullable=False, default=18)
    gst_amount: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["Job"] = relationship(back_populates="quotations")
    line_items: Mapped[list["LineItem"]] = relationship(
        back_populates="quotation",
        order_by="LineItem.position",
        foreign_keys="LineItem.quotation_id",
    )


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("quotations.id"))
    invoice_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # INV-0001
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unpaid")  # unpaid | paid
    subtotal: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    gst_rate: Mapped[object] = mapped_column(Numeric(5, 2), nullable=False, default=18)
    gst_amount: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    due_date: Mapped[str | None] = mapped_column(Date)
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["Job"] = relationship(back_populates="invoices")
    quotation: Mapped["Quotation"] = relationship()
    line_items: Mapped[list["LineItem"]] = relationship(
        back_populates="invoice",
        order_by="LineItem.position",
        foreign_keys="LineItem.invoice_id",
    )


class LineItem(Base):
    """Belongs to a quotation OR an invoice (approve copies quotation items
    into new rows pointing at the invoice)."""

    __tablename__ = "line_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("quotations.id"))
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id"))
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, default=1)
    unit: Mapped[str | None] = mapped_column(String(20))  # sqft, nos, lumpsum...
    rate: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    amount: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    quotation: Mapped["Quotation"] = relationship(
        back_populates="line_items", foreign_keys=[quotation_id]
    )
    invoice: Mapped["Invoice"] = relationship(
        back_populates="line_items", foreign_keys=[invoice_id]
    )


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    certificate_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # CERT-0001
    scope_summary: Mapped[str | None] = mapped_column(Text)
    issued_on: Mapped[str | None] = mapped_column(Date)
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["Job"] = relationship(back_populates="certificates")


class Document(Base):
    """Uploaded files (bills, receipts) extracted by Gemini in the background."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id"))
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")  # uploaded | extracted | failed
    doc_type: Mapped[str | None] = mapped_column(String(50))
    vendor_name: Mapped[str | None] = mapped_column(String(200))
    total_amount: Mapped[object] = mapped_column(Numeric(12, 2))
    document_date: Mapped[str | None] = mapped_column(Date)
    due_date: Mapped[str | None] = mapped_column(Date)
    expense_category: Mapped[str | None] = mapped_column(String(100))
    extracted_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["Job"] = relationship(back_populates="documents")


class JobEvent(Base):
    """Timeline entries shown on the job detail screen."""

    __tablename__ = "job_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["Job"] = relationship(back_populates="events")


# Read-only view for text-to-SQL search. One row per searchable record with a
# uniform shape; the search router only ever SELECTs from this.
SEARCH_VIEW_SQL = """
CREATE OR REPLACE VIEW v_search AS
SELECT 'job'::text          AS record_type,
       j.id                 AS id,
       j.job_number         AS number,
       e.name               AS party_name,
       NULL::numeric(12,2)  AS amount,
       j.status             AS status,
       j.created_at::date   AS record_date,
       j.id                 AS job_id,
       j.title              AS job_title
FROM jobs j
JOIN entities e ON e.id = j.customer_id

UNION ALL
SELECT 'quotation', q.id, q.quotation_number, e.name, q.total, q.status,
       q.created_at::date, q.job_id, j.title
FROM quotations q
JOIN jobs j ON j.id = q.job_id
JOIN entities e ON e.id = j.customer_id

UNION ALL
SELECT 'invoice', i.id, i.invoice_number, e.name, i.total, i.status,
       i.created_at::date, i.job_id, j.title
FROM invoices i
JOIN jobs j ON j.id = i.job_id
JOIN entities e ON e.id = j.customer_id

UNION ALL
SELECT 'certificate', c.id, c.certificate_number, e.name, NULL::numeric(12,2),
       'issued', COALESCE(c.issued_on, c.created_at::date), c.job_id, j.title
FROM certificates c
JOIN jobs j ON j.id = c.job_id
JOIN entities e ON e.id = j.customer_id

UNION ALL
SELECT 'document', d.id, d.filename, d.vendor_name, d.total_amount, d.status,
       COALESCE(d.document_date, d.created_at::date), d.job_id,
       COALESCE(j.title, '')
FROM documents d
LEFT JOIN jobs j ON j.id = d.job_id;
"""
