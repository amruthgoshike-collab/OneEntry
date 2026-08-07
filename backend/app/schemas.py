"""Pydantic request/response models.

Shapes here are the contract in `api_contract.md` — change both together.

Every Numeric column serializes as a decimal string ("12500.00"), never a
JSON float. `Money` is the annotation that does it.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, computed_field


def _decimal_str(v: Decimal | None) -> str | None:
    return None if v is None else f"{Decimal(v):.2f}"


Money = Annotated[Decimal, PlainSerializer(_decimal_str, return_type=str)]
MoneyOpt = Annotated[
    Optional[Decimal], PlainSerializer(_decimal_str, return_type=Optional[str])
]

ORM = ConfigDict(from_attributes=True, populate_by_name=True)

EntityType = Literal["customer", "vendor"]
JobStatus = Literal["enquiry", "quoted", "approved", "in_progress", "completed"]


# --- entities ---------------------------------------------------------------

class EntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: EntityType = "customer"
    gstin: str | None = Field(default=None, max_length=15)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=200)
    address: str | None = None


class Entity(BaseModel):
    model_config = ORM

    id: uuid.UUID
    name: str
    type: str
    gstin: str | None
    phone: str | None
    email: str | None
    address: str | None
    created_at: datetime


class EntityList(BaseModel):
    items: list[Entity]


# --- line items, shared by quotations and invoices ---------------------------

class LineItem(BaseModel):
    model_config = ORM

    id: uuid.UUID
    position: int
    description: str
    hsn_sac: str | None
    quantity: Money
    unit: str | None
    rate: Money
    tax_rate: Money
    amount: Money


# --- artifacts that hang off a job -------------------------------------------

class QuotationCreate(BaseModel):
    notes: str | None = None


class Quotation(BaseModel):
    model_config = ORM

    id: uuid.UUID
    job_id: uuid.UUID
    quotation_number: str
    status: str
    notes: str | None
    subtotal: Money
    gst_rate: Money
    gst_amount: Money
    total: Money
    created_at: datetime
    line_items: list[LineItem] = []
    # Filesystem path stays server-side; the API exposes a fetchable URL.
    pdf_path: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def pdf_url(self) -> str | None:
        return f"/api/quotations/{self.id}/pdf" if self.pdf_path else None


class Invoice(BaseModel):
    model_config = ORM

    id: uuid.UUID
    job_id: uuid.UUID
    quotation_id: uuid.UUID | None
    invoice_number: str
    status: str
    subtotal: Money
    gst_rate: Money
    gst_amount: Money
    total: Money
    due_date: date | None
    created_at: datetime
    line_items: list[LineItem] = []
    pdf_path: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def pdf_url(self) -> str | None:
        return f"/api/invoices/{self.id}/pdf" if self.pdf_path else None


class ApproveResponse(BaseModel):
    """POST /quotations/{id}/approve — both sides of the hand-off."""

    quotation: Quotation
    invoice: Invoice


class Certificate(BaseModel):
    model_config = ORM

    id: uuid.UUID
    job_id: uuid.UUID
    certificate_number: str
    scope_summary: str | None
    issued_on: date | None
    created_at: datetime
    pdf_path: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def pdf_url(self) -> str | None:
        return f"/api/certificates/{self.id}/pdf" if self.pdf_path else None


class Document(BaseModel):
    model_config = ORM

    id: uuid.UUID
    job_id: uuid.UUID | None
    filename: str
    status: str
    doc_type: str | None
    vendor_name: str | None
    total_amount: MoneyOpt
    document_date: date | None
    due_date: date | None
    expense_category: str | None
    summary: str | None
    extracted_json: dict | None
    created_at: datetime


class DocumentList(BaseModel):
    items: list[Document]


class JobEvent(BaseModel):
    model_config = ORM

    id: uuid.UUID
    job_id: uuid.UUID
    event_type: str
    detail: str | None
    created_at: datetime


# --- jobs --------------------------------------------------------------------

class JobCreate(BaseModel):
    customer_id: uuid.UUID
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    site_address: str | None = None


class JobUpdate(BaseModel):
    """All fields optional. Only keys actually sent are applied."""

    status: JobStatus | None = None
    completed_on: date | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    site_address: str | None = None


class JobBase(BaseModel):
    model_config = ORM

    id: uuid.UUID
    job_number: str
    customer_id: uuid.UUID
    title: str
    description: str | None
    site_address: str | None
    status: str
    completed_on: date | None
    created_at: datetime


class JobSummary(JobBase):
    """List row. Counts are computed in the query, not stored."""

    customer_name: str
    quotation_count: int
    invoice_count: int
    has_certificate: bool


class JobDetail(JobBase):
    """Drives the job detail screen — the whole demo hangs off this shape."""

    customer: Entity
    quotations: list[Quotation] = []
    invoices: list[Invoice] = []
    certificates: list[Certificate] = []
    documents: list[Document] = []
    events: list[JobEvent] = []


class JobList(BaseModel):
    items: list[JobSummary]


# --- search ------------------------------------------------------------------

class SearchRequest(BaseModel):
    q: str = Field(min_length=1, max_length=500)


class SearchResponse(BaseModel):
    mode: Literal["structured", "semantic"]
    answer: str
    # Present only on the structured path. Show it behind a toggle.
    sql: str | None = None
    # Free-form: a record listing echoes the v_search columns, but an
    # aggregation ("how many jobs are completed") returns whatever the SQL
    # selected. Render the keys as table headers.
    results: list[dict] = []
