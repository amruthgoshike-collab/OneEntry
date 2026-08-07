# OneEntry — API Contract

Base URL: `http://localhost:8000/api`

**This file is the agreement between the frontend and backend branches.**
Change it here first, tell the other person, then implement. All IDs are UUID
strings. **Every numeric DB column serializes as a string decimal**
(`"12500.00"`, gst_rate `"18.00"`, quantity `"3000.00"`) to avoid float drift.
Dates are `YYYY-MM-DD`, timestamps ISO 8601. Absent values are `null` — fields
are never omitted.

Implemented so far: **entities, jobs, documents, quotation generation,
approve-to-invoice, completion certificates** — the whole loop. Search is still
to be built.

`pdf_url` is an API path, not a filesystem path — `GET` it to receive
`application/pdf`. It is `null` until the PDF has been rendered.

---

## Entities

`POST /entities` → `201`
```json
{ "name": "ABC Constructions", "type": "customer",
  "gstin": "36AABCU9603R1ZM", "phone": "9876543210",
  "email": "abc@x.com", "address": "Hyderabad" }
```
`name` required. `type` is `customer` | `vendor`, defaults to `customer`.
Everything else optional. Returns the created **Entity**:
```json
{ "id": "uuid", "name": "ABC Constructions", "type": "customer",
  "gstin": "36AABCU9603R1ZM", "phone": "9876543210", "email": "abc@x.com",
  "address": "Hyderabad", "created_at": "2026-08-07T12:00:00Z" }
```

`GET /entities?type=customer&q=abc` → `200` `{ "items": [Entity] }`
Both params optional. `q` is a case-insensitive substring match on `name`.
Sorted by name.

---

## Jobs — the spine

`POST /jobs` → `201`
```json
{ "customer_id": "uuid", "title": "Office painting - 3000 sqft",
  "description": "Interior painting, 2 coats, Asian Paints Royale, 3rd floor",
  "site_address": "Gachibowli" }
```
`customer_id` and `title` required. Returns the full **JobDetail** shape below,
with a generated `job_number` (`JOB-0001`), `status: "enquiry"`, and one
`job_created` event already in `events`.
`404` if the customer doesn't exist, `400` if that entity is a vendor.

`GET /jobs` → `200` `{ "items": [JobSummary] }`, newest first.
**JobSummary** is the flat job fields plus `customer_name`, `quotation_count`,
`invoice_count`, `has_certificate` — no nested collections:
```json
{ "id": "uuid", "job_number": "JOB-0001", "customer_id": "uuid",
  "title": "Office painting - 3000 sqft", "description": "...",
  "site_address": "Gachibowli", "status": "enquiry", "completed_on": null,
  "created_at": "2026-08-07T12:00:00Z", "customer_name": "ABC Constructions",
  "quotation_count": 1, "invoice_count": 0, "has_certificate": false }
```

`GET /jobs/{id}` → `200` — full job. **This response drives the job detail
screen and the whole demo.**
```json
{ "id": "uuid", "job_number": "JOB-0001", "customer_id": "uuid",
  "title": "Office painting - 3000 sqft", "description": "...",
  "site_address": "Gachibowli", "status": "enquiry", "completed_on": null,
  "created_at": "2026-08-07T12:00:00Z",
  "customer": { Entity },
  "quotations": [ { "id": "uuid", "job_id": "uuid",
      "quotation_number": "QTN-0001", "status": "draft", "notes": null,
      "subtotal": "100000.00", "gst_rate": "18.00", "gst_amount": "18000.00",
      "total": "118000.00", "pdf_url": null, "created_at": "...",
      "line_items": [ LineItem ] } ],
  "invoices": [ { "id": "uuid", "job_id": "uuid", "quotation_id": "uuid",
      "invoice_number": "INV-0001", "status": "unpaid",
      "subtotal": "100000.00", "gst_rate": "18.00", "gst_amount": "18000.00",
      "total": "118000.00", "due_date": null, "pdf_url": null,
      "created_at": "...", "line_items": [ LineItem ] } ],
  "certificates": [ { "id": "uuid", "job_id": "uuid",
      "certificate_number": "CERT-0001", "scope_summary": "...",
      "issued_on": "2026-08-08", "pdf_url": null, "created_at": "..." } ],
  "documents": [ Document ],
  "events": [ { "id": "uuid", "job_id": "uuid", "event_type": "job_created",
      "detail": "JOB-0001 created for ABC Constructions",
      "created_at": "..." } ] }
```
**LineItem**: `{ "id": "uuid", "position": 0, "description": "Wall putty - 2
coats", "hsn_sac": "995473", "quantity": "3000.00", "unit": "sqft",
"rate": "18.00", "tax_rate": "18.00", "amount": "54000.00" }`, ordered by
`position`. `hsn_sac` is the GST classification code printed on the PDF and may
be `null`; `tax_rate` is that line's GST percent — lines in one document can
carry different rates, and `quotations.gst_rate` is then the blended effective
rate. `events` is ordered oldest first. `404` if the job doesn't exist.

`PATCH /jobs/{id}` → `200` `{ "status": "completed", "completed_on": "2026-08-08" }`
Accepts any subset of `status`, `completed_on`, `title`, `description`,
`site_address` — only keys present in the body are applied. `status` must be one
of `enquiry` | `quoted` | `approved` | `in_progress` | `completed`. Setting
status to `completed` without a `completed_on` defaults it to today, because the
certificate needs a date. Returns the full JobDetail. `404` if not found.

### Job events

Every job state change appends to `events`, the timeline on the detail screen:

| event_type | written when |
|---|---|
| `job_created` | `POST /jobs` |
| `status_changed` | the job's `status` actually changes. `detail` reads `"enquiry -> completed"` |
| `quotation_generated` | `POST /jobs/{id}/quotation` |
| `quotation_approved` | `POST /quotations/{id}/approve` |
| `invoice_created` | `POST /quotations/{id}/approve` |
| `certificate_issued` | `POST /jobs/{id}/certificate` |
| `invoice_paid` | an invoice is settled. No endpoint raises this yet — only `scripts/seed.py` writes it, so demo timelines look complete |

---

## Generation — the money endpoints

`POST /jobs/{id}/quotation` → `201`
Body optional: `{ "notes": "include scaffolding" }` — the note is passed to
Gemini as an extra instruction and stored on the quotation.

Gemini receives the job title, description, site and customer, and returns
line items only: `description`, `hsn_sac`, `quantity`, `unit`, `rate`,
`tax_rate`. **It never returns amounts.** Every amount, the CGST/SGST split and
the total are computed in Python from quantity × rate, so the arithmetic on the
PDF always adds up. Unusable line items (missing description, quantity or rate)
are dropped rather than failing the request.

Returns the full `Quotation` with `line_items[]` and `pdf_url`. Takes 5–15s —
frontend must show a loading state. Side effects: writes a `quotation_generated`
event, and moves the job from `enquiry` to `quoted` (with its own
`status_changed` event).

`404` if the job doesn't exist. `502` if Gemini fails or returns nothing
usable. If the PDF render fails the quotation is still saved with its numbers
and `pdf_url` is `null` — the figures are the valuable part.

`GET /quotations/{id}/pdf` → `200 application/pdf`
What `pdf_url` points at. `404` if the quotation doesn't exist or has no
rendered PDF.

`POST /quotations/{id}/approve` → `200`
No body. Sets quotation `approved`, job `approved`, **and creates the invoice
by copying line items.** Returns `{ "quotation": Quotation, "invoice": Invoice }`.

The invoice copies the quotation's `subtotal`, `gst_rate`, `gst_amount` and
`total` verbatim, and each line item's `description`, `hsn_sac`, `quantity`,
`unit`, `rate`, `tax_rate`, `amount` and `position` into **new rows** carrying
`invoice_id` (the quotation keeps its own). `due_date` is 30 days out
(`INVOICE_DUE_DAYS`), `status` is `unpaid`, and the invoice PDF is rendered
before the response returns, so `pdf_url` is populated immediately.

**No LLM call here** — it copies rows that already exist. Measured at
**~370 ms** end to end including the PDF, against ~13 s to generate the
quotation. That contrast is the demo, so keep it that way.

Writes `quotation_approved` and `invoice_created` events, plus `status_changed`
if the job wasn't already `approved`.

`404` if the quotation doesn't exist. `409` if it is already approved —
approving twice would mint a second invoice for the same work.

`GET /invoices/{id}/pdf` → `200 application/pdf`
What the invoice's `pdf_url` points at. `404` if the invoice doesn't exist or
has no rendered PDF.

`GET /quotations` → `200` `{ "items": [QuotationSummary] }`, newest first.
Flat list rows for the Quotations screen — no line items:
```json
{ "id": "uuid", "job_id": "uuid", "quotation_number": "QTN-0001",
  "status": "approved", "total": "809556.70", "created_at": "...",
  "job_number": "JOB-0001", "job_title": "MS railing and staircase…",
  "customer_name": "Sai Ram Constructions", "line_item_count": 3,
  "pdf_url": "/api/quotations/{id}/pdf" }
```

`GET /invoices` → `200` `{ "items": [InvoiceSummary] }`, newest first.
Same shape plus `quotation_number`, `due_date`, minus `line_item_count`.

`POST /jobs/{id}/certificate` → `201`
No body. **Requires job status `completed`** — `409` otherwise, with a message
naming the current status. Gemini writes `scope_summary` from the job title,
description and the billed line items (invoice line items, falling back to
quotation line items): 3-4 sentences, one paragraph, past tense, no bullets and
no marketing language. Bullets and line breaks are stripped server-side rather
than trusted. Returns `Certificate` with `pdf_url`; takes 5-15s.

Writes a `certificate_issued` event. `404` if the job doesn't exist, `502` if
Gemini fails or returns an empty summary.

Reissuing is allowed — a job may hold several certificates (`CERT-0002`, …),
and `GET /jobs/{id}` returns them all in `certificates[]`.

The warranty period printed on the certificate comes from the `WARRANTY_MONTHS`
setting, not from the database — it is company policy rather than per-job data.

`GET /certificates/{id}/pdf` → `200 application/pdf`
What the certificate's `pdf_url` points at. `404` if the certificate doesn't
exist or has no rendered PDF.

---

## Documents

`POST /documents` — `multipart/form-data`, field `file`, optional `job_id`
→ `202` `{ "id": "uuid", "status": "uploaded" }`
The file is saved under `backend/storage/YYYY/MM/` and extraction runs in a
background task, so this returns immediately. `415` if the file is not a PDF,
PNG, JPEG or WebP — those are what Gemini reads natively. `400` if empty,
`404` if `job_id` is given but no such job exists.

`GET /documents/{id}` → `200` — poll until `status` is `extracted` or `failed`.
**Document**:
```json
{ "id": "uuid", "job_id": null, "filename": "sunrise-invoice.png",
  "status": "extracted", "doc_type": "invoice",
  "vendor_name": "SUNRISE HARDWARE & PAINTS", "total_amount": "36182.00",
  "document_date": "2026-01-14", "due_date": "2026-02-13",
  "expense_category": "materials",
  "summary": "Purchased paint, wall putty and rollers from Sunrise Hardware.",
  "extracted_json": { ... },
  "created_at": "2026-08-07T12:00:00Z" }
```
`status` is `uploaded` | `extracted` | `failed`. While `uploaded`, every
extracted field is `null`. On `failed`, `extracted_json` holds
`{ "error": "..." }` so the frontend can show why.

`doc_type` is exactly one of `invoice`, `bill`, `receipt`, `certificate`,
`other` — a tax/GST invoice is `invoice`, an electricity or any utility bill is
`bill`. Anything Gemini returns outside this list is stored as `other`.
`expense_category` is one of `materials`, `labour`, `transport`, `utilities`,
`equipment_rental`, `fuel`, `professional_fees`, `permits`, `office`, `other`.
Both fall back to `other` rather than erroring on an unexpected value.

`extracted_json` is Gemini's full reply, which holds more than the columns do —
`line_items[]`, `vendor_gstin`, `document_number`, `subtotal`, `tax_amount`,
`notes`. Treat every key in it as optional.

Amount conventions: every charge appears exactly once — as a line item or
inside `tax_amount`, never both. `tax_amount` is actual GST/VAT only; statutory
duties and surcharges are line items (so a no-GST utility bill has
`tax_amount: null`). After extraction the backend checks that line items sum to
`subtotal` and that `subtotal + tax_amount = total_amount` (± ₹0.50 printed
round-off). On a mismatch the numbers are still stored, but `extracted_json`
gains a `validation_warnings: ["..."]` array and a warning is logged — never
silently trusted.

`summary` is a one-line recap and is the text that gets embedded into ChromaDB
for fuzzy recall, so it is a real column rather than just a key in
`extracted_json`.

`GET /documents` → `200` `{ "items": [Document] }`, newest first.

---

## Search — plain English

`POST /search` → `200`
```json
{ "q": "invoices from ABC above 20000" }
```
```json
{ "mode": "structured",
  "answer": "3 invoices totalling ₹1,84,500.",
  "sql": "SELECT ... FROM v_search WHERE ...",
  "results": [ { "record_type": "invoice", "number": "INV-0007",
                 "party_name": "ABC Constructions", "amount": "72000.00",
                 "status": "unpaid", "record_date": "2026-07-14" } ] }
```
`mode` is `structured` or `semantic`. Frontend renders both the same way —
`answer` on top, `results` as a table. Show `sql` behind a toggle; judges like
seeing it. `sql` is `null` on the semantic path.

**Routing.** Any filterable signal in the question — a digit, a comparison
(`above`, `more than`), an aggregation (`how many`, `most`), a status word
(`unpaid`, `completed`) or a date (`last month`, `March`) — goes structured.
Only a question with no filterable content at all falls through to semantic,
so "when in doubt" always lands on structured.

**`results` is free-form.** A record listing echoes the `v_search` columns
above, but an aggregation returns whatever the SQL selected — `how many jobs
are completed` yields `[{"completed_jobs_count": 3}]`. Render the keys of the
first row as table headers rather than assuming a fixed shape. Semantic results
add `id`, `job_id` and `job_title`.

**Safety.** The generated SQL is validated before execution: a single plain
SELECT (no `WITH`), no comments, no semicolons, no DDL/DML keywords,
`v_search` as the only readable relation, and `LIMIT 50` forced on. Anything
else is rejected unexecuted. If the SQL is rejected, fails to run, or Gemini is
unavailable, the request falls back to the semantic path rather than erroring —
so `mode` may be `semantic` for a question that looks structured.

`502` only if both paths fail.

---

## Errors

Every failure: `{ "detail": "human readable message" }` with a real status code.
Never return 200 with an error body.

This includes request-validation failures: FastAPI's default 422 body is a list
of error objects, so `main.py` installs a handler that flattens it to a single
string — `{ "detail": "title: String should have at least 1 character" }`.
