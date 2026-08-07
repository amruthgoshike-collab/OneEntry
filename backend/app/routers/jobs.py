import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.db import get_db
from app.events import log_event
from app.numbering import next_number
from app.search.chroma import index_job

router = APIRouter(tags=["jobs"])


def _load_detail(db: Session, job_id: uuid.UUID) -> models.Job:
    """Job with every child collection eagerly loaded, or 404."""
    stmt = (
        select(models.Job)
        .where(models.Job.id == job_id)
        .options(
            selectinload(models.Job.customer),
            selectinload(models.Job.quotations).selectinload(
                models.Quotation.line_items
            ),
            selectinload(models.Job.invoices).selectinload(models.Invoice.line_items),
            selectinload(models.Job.certificates),
            selectinload(models.Job.documents),
            selectinload(models.Job.events),
        )
    )
    job = db.execute(stmt).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.post("/jobs", response_model=schemas.JobDetail, status_code=201)
def create_job(payload: schemas.JobCreate, db: Session = Depends(get_db)):
    customer = db.get(models.Entity, payload.customer_id)
    if customer is None:
        raise HTTPException(
            status_code=404, detail=f"Customer {payload.customer_id} not found"
        )
    if customer.type != "customer":
        raise HTTPException(
            status_code=400,
            detail=f"Entity {customer.name} is a {customer.type}, not a customer",
        )

    job = models.Job(
        **payload.model_dump(),
        job_number=next_number(db, models.Job.job_number, "JOB"),
        status="enquiry",
    )
    db.add(job)
    db.flush()  # assign job.id before the event references it
    log_event(db, job.id, "job_created", f"{job.job_number} created for {customer.name}")
    db.commit()

    detail = _load_detail(db, job.id)
    index_job(detail)  # best-effort; never fails the request
    return detail


@router.get("/jobs", response_model=schemas.JobList)
def list_jobs(db: Session = Depends(get_db)):
    def count_of(model):
        return (
            select(func.count(model.id))
            .where(model.job_id == models.Job.id)
            .scalar_subquery()
        )

    stmt = (
        select(
            models.Job,
            models.Entity.name,
            count_of(models.Quotation),
            count_of(models.Invoice),
            count_of(models.Certificate),
        )
        .join(models.Entity, models.Entity.id == models.Job.customer_id)
        .order_by(models.Job.created_at.desc())
    )

    items = [
        schemas.JobSummary(
            **schemas.JobBase.model_validate(job).model_dump(),
            customer_name=customer_name,
            quotation_count=quotations,
            invoice_count=invoices,
            has_certificate=certificates > 0,
        )
        for job, customer_name, quotations, invoices, certificates in db.execute(stmt)
    ]
    return {"items": items}


@router.get("/jobs/{job_id}", response_model=schemas.JobDetail)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    return _load_detail(db, job_id)


@router.patch("/jobs/{job_id}", response_model=schemas.JobDetail)
def update_job(
    job_id: uuid.UUID, payload: schemas.JobUpdate, db: Session = Depends(get_db)
):
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    changes = payload.model_dump(exclude_unset=True)
    previous_status = job.status
    for field, value in changes.items():
        setattr(job, field, value)

    if "status" in changes and changes["status"] != previous_status:
        # A certificate needs a completion date, so don't leave it unset.
        if job.status == "completed" and job.completed_on is None:
            job.completed_on = date.today()
        log_event(
            db,
            job.id,
            "status_changed",
            f"{previous_status} -> {job.status}",
        )

    db.commit()
    detail = _load_detail(db, job.id)
    index_job(detail)
    return detail
