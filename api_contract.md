# OneEntry — API Contract

Base URL: `http://localhost:8000/api`

**This file is the agreement between the frontend and backend branches.**
Change it here first, tell the other person, then implement. All IDs are UUID
strings. All money is a string decimal (`"12500.00"`) to avoid float drift.

---

## Entities

`POST /entities` → `201`
```json
{ "name": "ABC Constructions", "type": "customer",
  "gstin": "36AABCU9603R1ZM", "phone": "9876543210",
  "email": "abc@x.com", "address": "Hyderabad" }
```
Returns the created entity with `id` and `created_at`.

`GET /entities?type=customer&q=abc` → `200` `{ "items": [Entity] }`

---

## Jobs — the spine

`POST /jobs` → `201`
```json
{ "customer_id": "uuid", "title": "Office painting - 3000 sqft",
  "description": "Interior painting, 2 coats, Asian Paints Royale, 3rd floor",
  "site_address": "Gachibowli" }
```
Returns `Job` with generated `job_number` (`JOB-0001`) and `status: "enquiry"`.

`GET /jobs` → `200` `{ "items": [JobSummary] }`
JobSummary adds `customer_name`, `quotation_count`, `invoice_count`,
`has_certificate`.

`GET /jobs/{id}` → `200` — full job with nested `quotations`, `invoices`,
`certificates`, `documents`, `events`. **This response drives the job detail
screen and the whole demo.**

`PATCH /jobs/{id}` → `200` `{ "status": "completed", "completed_on": "2026-08-08" }`

---

## Generation — the money endpoints

`POST /jobs/{id}/quotation` → `201`
Body optional: `{ "notes": "include scaffolding" }`
Backend sends the job description to Gemini, gets structured line items back,
computes GST, persists, renders PDF. Returns `Quotation` with `line_items[]`
and `pdf_url`. Takes 5–15s — frontend must show a loading state.

`POST /quotations/{id}/approve` → `200`
Sets quotation `approved`, job `approved`, **and creates the invoice by copying
line items.** Returns `{ "quotation": Quotation, "invoice": Invoice }`.
No LLM call here. It must be instant — that contrast is the demo.

`POST /jobs/{id}/certificate` → `201`
Requires job status `completed`. Gemini writes `scope_summary` from the job and
its line items. Returns `Certificate` with `pdf_url`.

---

## Documents

`POST /documents` — `multipart/form-data`, field `file`, optional `job_id`
→ `202` `{ "id": "uuid", "status": "uploaded" }`
Extraction runs in a background task.

`GET /documents/{id}` → `200` — poll until `status` is `extracted` or `failed`.
When extracted: `doc_type`, `vendor_name`, `total_amount`, `document_date`,
`due_date`, `expense_category`, `extracted_json`.

`GET /documents` → `200` `{ "items": [Document] }`

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
seeing it.

---

## Errors

Every failure: `{ "detail": "human readable message" }` with a real status code.
Never return 200 with an error body.
