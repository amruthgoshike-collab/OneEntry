import logging
import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import STORAGE_ROOT
from app.db import SessionLocal, get_db
from app.extraction import extract_from_bytes, guess_mime_type
from app.llm.client import SUPPORTED_MIME_TYPES

logger = logging.getLogger(__name__)
router = APIRouter(tags=["documents"])

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _save_upload(filename: str, data: bytes) -> Path:
    """Write to backend/storage/YYYY/MM/ and return the path."""
    now = datetime.now()
    folder = STORAGE_ROOT / f"{now:%Y}" / f"{now:%m}"
    folder.mkdir(parents=True, exist_ok=True)

    # Path components in the client-supplied name are stripped, not trusted.
    stem = _UNSAFE.sub("_", Path(filename).name).strip("_") or "upload"
    path = folder / f"{uuid.uuid4().hex[:8]}_{stem}"
    path.write_bytes(data)
    return path


def run_extraction(document_id: uuid.UUID) -> None:
    """Background task: read the saved file, ask Gemini, fill the columns.

    Opens its own session — the request's session is already closed by now.
    """
    with SessionLocal() as db:
        document = db.get(models.Document, document_id)
        if document is None:
            logger.error("Extraction skipped: document %s vanished", document_id)
            return
        try:
            file_bytes = Path(document.storage_path).read_bytes()
            mime_type = guess_mime_type(document.filename)
            fields = extract_from_bytes(file_bytes, mime_type, document.filename)
            for column, value in fields.items():
                setattr(document, column, value)
            document.status = "extracted"
        except Exception as exc:
            logger.exception("Extraction failed for document %s", document_id)
            document.status = "failed"
            # Keep the reason where the frontend can surface it.
            document.extracted_json = {"error": f"{type(exc).__name__}: {exc}"}
        db.commit()


@router.post("/documents", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    job_id: uuid.UUID | None = Form(default=None),
    db: Session = Depends(get_db),
):
    mime_type = guess_mime_type(file.filename or "", file.content_type)
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"{file.filename or 'file'} is {mime_type or 'an unknown type'}. "
                "Upload a PDF, PNG, JPEG or WebP."
            ),
        )

    if job_id is not None and db.get(models.Job, job_id) is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    path = _save_upload(file.filename or "upload", data)
    document = models.Document(
        job_id=job_id,
        filename=Path(file.filename or path.name).name,
        storage_path=str(path),
        status="uploaded",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(run_extraction, document.id)
    return {"id": str(document.id), "status": document.status}


@router.get("/documents", response_model=schemas.DocumentList)
def list_documents(db: Session = Depends(get_db)):
    stmt = select(models.Document).order_by(models.Document.created_at.desc())
    return {"items": db.execute(stmt).scalars().all()}


@router.get("/documents/{document_id}", response_model=schemas.Document)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    document = db.get(models.Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return document
