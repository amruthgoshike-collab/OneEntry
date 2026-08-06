from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import documents, entities, jobs, quotations

app = FastAPI(title="OneEntry API")

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
