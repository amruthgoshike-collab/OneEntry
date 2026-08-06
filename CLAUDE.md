# OneEntry

**Enter a job once — quotation, invoice, and certificate generate themselves.**

Hackathon build (Quantum Arena). Optimize for a working end-to-end demo, not
production hardening.

## The one loop that must work

1. User creates a **Job** (customer + description), or uploads a document that
   becomes one.
2. AI generates a **Quotation** from the job description.
3. Quotation is approved → **Invoice** generates from it. No retyping.
4. Job marked complete → **Completion Certificate** generates from it.
5. Everything is queryable in plain English.

If a feature does not serve this loop, it does not get built.

## Architecture

- `jobs` is the spine. Quotations, invoices, certificates, and documents all
  carry `job_id`. This lineage IS the product — never create a quotation or
  invoice that isn't attached to a job.
- Backend: FastAPI + SQLAlchemy + Supabase Postgres.
- Frontend: React + Vite + Tailwind.
- LLM: Gemini, called ONLY through `backend/app/llm/client.py`.
- Vector search: ChromaDB, local persistent client.
- PDFs: WeasyPrint rendering Jinja2 HTML templates in `backend/app/templates/`.

## Hard rules

- **Never invent DB columns.** Read `backend/app/models.py` first. If a column
  is missing, say so and propose a migration — do not silently add it.
- **The LLM never produces layout.** It returns structured JSON only. Jinja2
  templates own all PDF/document formatting.
- **No OCR library.** Gemini reads PDFs and images natively. Do not add
  PaddleOCR, Tesseract, or pytesseract.
- **API changes go through `api_contract.md` first.** Update that file in the
  same change, or frontend and backend will diverge.
- Money is `Numeric(12, 2)`. Never float.
- All Gemini calls must handle malformed JSON — strip markdown fences, retry
  once, then fail loudly with the raw response logged.

## Natural-language query routing

Two paths, chosen by a router in `backend/app/search/router.py`:

- **Structured / numeric** ("invoices above 20000", "jobs from ABC Constructions")
  → Gemini text-to-SQL against the read-only view `v_search`. Never against raw
  tables, never anything but SELECT.
- **Fuzzy recall** ("that painting quotation from January") → ChromaDB semantic
  search over document and job summaries.

Pure vector search fails numeric filters. Do not route numbers to Chroma.

## Layout

```
backend/
  app/
    main.py            FastAPI app + routers
    config.py          settings from .env
    models.py          SQLAlchemy models — SOURCE OF TRUTH for schema
    schemas.py         Pydantic request/response models
    db.py              engine + session
    numbering.py       JOB-0001 / QTN-0001 / INV-0001 sequences
    events.py          job timeline rows
    routers/           entities.py, jobs.py, documents.py, quotations.py,
                       invoices.py, certificates.py, search.py
    llm/client.py      ALL Gemini calls go here
    llm/prompts.py     prompt templates
    pdf/render.py      HTML -> PDF
    templates/         quotation.html, invoice.html, certificate.html
    search/router.py   structured vs semantic routing
  scripts/
    init_db.py         create tables + v_search view, re-runnable
  tests/
    test_extract.py    runs extraction over samples/ and prints JSON
frontend/
  src/
samples/               real invoices/bills for testing extraction
api_contract.md        agreed endpoints + JSON shapes
```

## Commands

```bash
# backend
cd backend && uvicorn app.main:app --reload --port 8000
cd backend && python -m tests.test_extract        # extraction smoke test

# frontend
cd frontend && npm run dev
```

## Branching

`main` holds shared contracts: `models.py`, `schemas.py`, `api_contract.md`.
Feature work happens on `backend` and `frontend` branches. If a change touches
a shared contract file, land it on `main` first and rebase.

## Explicitly out of scope

WhatsApp/Instagram ingestion, attendance tracking, multi-tenant auth, real
reminder scheduling, inventory. Do not build these. Do not suggest them.
