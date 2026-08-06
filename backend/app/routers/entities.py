from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db

router = APIRouter(tags=["entities"])


@router.post("/entities", response_model=schemas.Entity, status_code=201)
def create_entity(payload: schemas.EntityCreate, db: Session = Depends(get_db)):
    entity = models.Entity(**payload.model_dump())
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.get("/entities", response_model=schemas.EntityList)
def list_entities(
    db: Session = Depends(get_db),
    entity_type: schemas.EntityType | None = Query(default=None, alias="type"),
    q: str | None = Query(default=None, description="case-insensitive name match"),
):
    stmt = select(models.Entity).order_by(models.Entity.name)
    if entity_type:
        stmt = stmt.where(models.Entity.type == entity_type)
    if q:
        stmt = stmt.where(models.Entity.name.ilike(f"%{q}%"))
    return {"items": db.execute(stmt).scalars().all()}
