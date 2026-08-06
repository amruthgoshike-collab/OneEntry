# OneEntry — API Contract

Base URL: `http://localhost:8000/api`

**This file is the agreement between the frontend and backend branches.**
Change it here first, tell the other person, then implement. All IDs are UUID
strings. **Every numeric DB column serializes as a string decimal**
(`"12500.00"`, gst_rate `"18.00"`, quantity `"3000.00"`) to avoid float drift.
Dates are `YYYY-MM-DD`, timestamps ISO 8601. Absent values are `null` — fields
are never omitted.

Implemented so far: **entities, jobs**. Generation, documents and search are
still to be built.

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
**LineItem**: `{ "id": "uuid", "position": 0, "description": "Wall putty",
"quantity": "3000.00", "unit": "sqft", "rate": "18.00", "amount": "54000.00" }`,
ordered by `position`. `events` is ordered oldest first.
`404` if the job doesn't exist.

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
| `status_changed` | `PATCH /jobs/{id}` actually changes `status`. `detail` reads `"enquiry -> completed"` |

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

This includes request-validation failures: FastAPI's default 422 body is a list
of error objects, so `main.py` installs a handler that flattens it to a single
string — `{ "detail": "title: String should have at least 1 character" }`.
