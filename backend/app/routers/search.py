from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db
from app.llm.client import GeminiError
from app.search.router import search

router = APIRouter(tags=["search"])


@router.post("/search", response_model=schemas.SearchResponse)
def run_search(payload: schemas.SearchRequest, db: Session = Depends(get_db)):
    try:
        result = search(db, payload.q.strip())
    except GeminiError as exc:
        raise HTTPException(status_code=502, detail=f"Search failed: {exc}")
    except Exception as exc:
        # Most likely a valid-looking SELECT the database still rejected.
        raise HTTPException(status_code=502, detail=f"Search failed: {exc}")

    return {
        "mode": result.mode,
        "answer": result.answer,
        "sql": result.sql,
        "results": result.results,
    }
