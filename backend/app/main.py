from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.pdf.render import warm_up as warm_up_pdf
from app.routers import (
    certificates,
    documents,
    entities,
    invoices,
    jobs,
    quotations,
    search,
)
from app.search.chroma import warm_up as warm_up_chroma


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Chromium costs ~300ms to start and the embedding model rather more. Pay
    # both at boot rather than on the first approval or job creation. Each
    # warms on its own thread and tolerates its own failure.
    warm_up_pdf()
    warm_up_chroma()
    yield


app = FastAPI(title="OneEntry API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Flatten FastAPI's list-shaped 422 body into the contract's
    `{"detail": "human readable message"}`."""
    messages = []
    for error in exc.errors():
        field = ".".join(
            str(part)
            for part in error["loc"]
            if part not in ("body", "query", "path", "header")
        )
        messages.append(f"{field}: {error['msg']}" if field else error["msg"])
    return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(entities.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(quotations.router, prefix="/api")
app.include_router(invoices.router, prefix="/api")
app.include_router(certificates.router, prefix="/api")
app.include_router(search.router, prefix="/api")
