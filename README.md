# OneEntry

**Enter a job once — quotation, invoice, and certificate generate themselves.**

Built at Quantum Arena 2026.

---

## The problem

A construction contractor gets a call at 9am. He writes the details on paper.
The customer asks for a quotation, so he opens Word, finds an old one, and
retypes the customer name, address, GSTIN, quantities, rates, GST, and payment
terms. Twenty minutes gone.

The customer approves. Now he makes the invoice — the same information, typed
a second time. His accountant then opens Tally and types it a third time. When
the job finishes, the customer wants a completion certificate, so he types it a
fourth time.

Eight months later the customer asks for that quotation again. He spends twenty
minutes searching WhatsApp, Downloads, Drive, and Desktop, and doesn't find it.

**The problem isn't that he lacks accounting software.** He has Tally. The
problem is that the same business information gets entered over and over, and
lives scattered across systems that don't talk to each other.

## What OneEntry does

You enter a job once. Everything downstream generates itself.

```
Job created
   └─ AI reads the description → Quotation (line items, GST, terms, PDF)
        └─ Customer approves → Invoice generated instantly, zero retyping
             └─ Job completed → Completion Certificate generated
```

Every document you upload — purchase bills, electricity bills, receipts — is
read by AI, structured, and attached to the job it belongs to. Then you ask for
things in plain English instead of digging through folders:

- *"invoices from ABC Constructions above 20000"*
- *"that painting quotation from January"*
- *"which jobs have unpaid invoices"*

## Why not just use Tally / Zoho / ERPNext?

Those are excellent accounting systems, and OneEntry doesn't replace them. They
record what already happened. OneEntry handles the repetitive work that happens
*before* accounting — turning an enquiry into a quotation into an invoice into a
certificate — which today is done by hand in Word and WhatsApp.

The unit of work in an ERP is a transaction. In OneEntry it's a **job**, and
every artifact hangs off it. That's the whole design.

## How it works

```
Job description ──► Gemini ──► structured JSON ──► Postgres
                                                      │
Uploaded document ──► Gemini (native PDF/image) ──────┤
                                                      │
                                    ┌─────────────────┴─────────────────┐
                                    │                                   │
                          Jinja2 → WeasyPrint              embeddings → ChromaDB
                              (PDF artifacts)              (semantic recall)
```

Plain-English search routes two ways: numeric and filtered questions become SQL
against a read-only view, fuzzy recall goes to vector search. Pure semantic
search can't answer "above ₹20,000", so it doesn't get asked to.

No OCR library — Gemini reads PDFs and images natively, which keeps document
layout as context instead of throwing it away.

## Stack

| Layer | Choice |
|---|---|
| Frontend | React, Vite, Tailwind |
| Backend | FastAPI, SQLAlchemy |
| Database | Supabase (Postgres + storage) |
| LLM | Gemini |
| Vector search | ChromaDB, all-MiniLM-L6-v2 |
| PDFs | Jinja2 + WeasyPrint |

## Running it

```bash
git clone https://github.com/amruthgoshike-collab/OneEntry.git
cd OneEntry

cp .env.example .env        # add Supabase + Gemini keys

cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install && npm run dev
```

Backend on `:8000`, frontend on `:5173`. API contract is in
[`api_contract.md`](./api_contract.md); the schema is the source of truth in
`backend/app/models.py`.

## Repository layout

```
backend/app/
  models.py        schema — jobs is the spine, everything FKs to it
  routers/         jobs, documents, quotations, invoices, certificates, search
  llm/client.py    every Gemini call goes through here
  pdf/render.py    HTML → PDF
  templates/       quotation.html, invoice.html, certificate.html
  search/router.py structured-SQL vs semantic routing
frontend/src/      React app
samples/           real documents used to test extraction
```

## Status

Hackathon build. Single-tenant, no auth, demo-scale. Reminders, WhatsApp
ingestion, and attendance are deliberately out of scope.

## Team

[@amruthgoshike-collab](https://github.com/amruthgoshike-collab) · Akshay
