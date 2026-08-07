"""Prompt templates. Every one of these must ask for JSON only — the LLM
never produces layout, Jinja2 templates own all formatting."""

DOC_TYPES = (
    "invoice",
    "bill",
    "receipt",
    "certificate",
    "other",
)

EXPENSE_CATEGORIES = (
    "materials",
    "labour",
    "transport",
    "utilities",
    "equipment_rental",
    "fuel",
    "professional_fees",
    "permits",
    "office",
    "other",
)

TEXT_TO_SQL_PROMPT = """You translate a contractor's plain-English question into ONE
read-only SQL SELECT statement.

You may query exactly one relation, the read-only view `v_search`. It has one row
per searchable record:

  record_type  text     'job' | 'quotation' | 'invoice' | 'certificate' | 'document'
  id           uuid     primary key of the underlying row
  number       text     JOB-0001 / QTN-0001 / INV-0001 / CERT-0001, or a filename
                        for documents
  party_name   text     the customer for jobs, quotations, invoices and
                        certificates; the vendor for documents
  amount       numeric  the total. NULL for jobs and certificates
  status       text     job: enquiry|quoted|approved|in_progress|completed
                        quotation: draft|approved
                        invoice: unpaid|paid
                        certificate: always 'issued'
                        document: uploaded|extracted|failed
  record_date  date     the date the record belongs to
  job_id       uuid     the job this record hangs off
  job_title    text     the job's title

Today is {today}.

Question: {question}

Return a JSON object with exactly one key:

{{ "sql": "SELECT ..." }}

Rules:
- A single plain SELECT. Never INSERT, UPDATE, DELETE or any DDL, no WITH
  clause, no semicolon, no SQL comments.
- `v_search` is the only relation you may name. Never reference the underlying
  tables.
- **Never use date functions** — no NOW(), CURRENT_DATE, date_trunc, strftime,
  INTERVAL. Work out the date bounds yourself from today's date above and write
  them as literal 'YYYY-MM-DD' strings. "last month" becomes
  record_date >= '2026-06-01' AND record_date < '2026-07-01' style bounds.
- **Portable SQL only** — this runs on both Postgres and SQLite. Never use
  ILIKE; for case-insensitive matching write
  LOWER(column) LIKE LOWER('%text%'). Avoid any other dialect-specific
  function.
- Match text loosely. A question about "electricity bills" should look at
  party_name, number and job_title with LOWER(...) LIKE, not just one column.
- Filter record_type whenever the question names a kind of record. "invoices"
  means record_type = 'invoice'.
- For counts and totals, return the aggregate — you do not have to return the
  standard columns. Give aggregate columns a readable alias.
- Otherwise select record_type, number, party_name, amount, status, record_date
  so the results render as a table.
- Order sensibly: newest first for listings, largest first for rankings.
- Return the JSON object only. No commentary, no markdown fences.
"""


SEARCH_ANSWER_PROMPT = """Answer the user's question in ONE short sentence, using only
the rows given.

Question: {question}

Rows returned ({row_count} total, showing up to 20):
{rows}

Return a JSON object with exactly one key:

{{ "answer": "..." }}

Rules:
- One sentence. State the finding directly; no preamble like "Based on the data".
- Use Indian digit grouping for money and prefix with the rupee sign, e.g.
  Rs.1,84,500 becomes "₹1,84,500".
- If there are no rows, say plainly that nothing matched — do not invent records.
- Do not list every row; summarise. Naming one or two is fine when there are few.
- Return the JSON object only. No commentary, no markdown fences.
"""


CERTIFICATE_PROMPT = """You are drafting the scope paragraph for a work completion
certificate that an Indian construction contractor issues to a customer once a job
is finished.

Job number:   {job_number}
Title:        {title}
Description:  {description}
Site:         {site_address}
Customer:     {customer_name}
Completed on: {completed_on}
Work carried out and billed:
{line_items}

Return a JSON object with exactly one key:

{{ "scope_summary": "the paragraph" }}

Write either 3 or 4 complete sentences — never five — as a SINGLE paragraph, in
the past tense, in the formal register an Indian contractor actually uses on a
completion certificate. Keep the whole paragraph between 60 and 100 words; it
has to fit one block on a printed certificate.

Rules:
- State what was done, using the real quantities, areas and materials from the
  billed work above. Be specific and factual.
- Plain professional English. No marketing language of any kind — never
  "premium", "world-class", "state-of-the-art", "high-quality", "hassle-free",
  "customer satisfaction", "we are proud", "we take pleasure".
- One paragraph. No bullet points, no numbered lists, no line breaks, no
  headings, no salutation, no sign-off.
- Do not invent work that is not in the description or the billed items.
- Do not write the certificate number, dates or signature lines — the template
  prints those separately.
- Return the JSON object only. No commentary, no markdown fences.
"""


QUOTATION_PROMPT = """You are preparing a priced quotation for an Indian construction
contractor. Turn the job below into billable line items a customer would accept.

Job number:  {job_number}
Title:       {title}
Description: {description}
Site:        {site_address}
Customer:    {customer_name}
{extra_notes}

Return a JSON object with exactly these keys:

{{
  "line_items": [
    {{ "description": specific and quotable, e.g. "Wall putty application - 2 coats,
                      including surface preparation",
       "hsn_sac": the HSN (goods) or SAC (services) code as a string,
       "quantity": decimal string,
       "unit": "sqft" | "rft" | "nos" | "bag" | "ltr" | "day" | "lumpsum",
       "rate": per-unit price in INR excluding GST, decimal string,
       "tax_rate": GST percent for this line as a decimal string }}
  ],
  "payment_terms": [ two or three short strings, e.g.
                     "40% advance along with work order" ],
  "validity_days": integer, typically 15,
  "notes": one short line on scope or assumptions, or null
}}

Rules:
- Do NOT compute amount, subtotal, tax or total. Return only quantity and rate;
  the system computes every amount in Python. Any totals you include are ignored.
- Break the work into 3 to 8 line items. Prefer real trade breakdowns
  (surface preparation, primer, putty, finish coats, scaffolding) over one
  vague "painting work" line.
- Quantities must follow the description. If it says 3000 sqft, use 3000.
- Use realistic 2026 Hyderabad market rates.
- SAC codes for construction and finishing services are in the 9954 family,
  e.g. 995473 for painting and finishing. Goods use their own HSN, e.g. 3209
  for paints, 3214 for putty. Use your best judgement per line.
- tax_rate is normally "18.00" for construction services. Use what is correct
  for the item.
- Return the JSON object only. No commentary, no markdown fences.
"""


DOCUMENT_EXTRACTION_PROMPT = f"""You are reading a business document that belongs to a small
Indian construction contractor. It may be a supplier bill, a tax invoice, a utility bill,
a receipt, or a delivery challan. It may be a photo, a scan, or a clean PDF.

Read the whole document, including tables and handwriting, and return a JSON object with
exactly these keys:

{{{{
  "doc_type": one of {list(DOC_TYPES)},
  "vendor_name": the business that ISSUED this document (who is being paid), as printed,
  "vendor_gstin": the vendor's GSTIN, or null,
  "document_number": the invoice/bill number as printed, or null,
  "document_date": issue date as "YYYY-MM-DD", or null,
  "due_date": payment due date as "YYYY-MM-DD", or null if not stated,
  "currency": ISO code, "INR" unless clearly otherwise,
  "subtotal": the sum of all line item amounts, before GST/VAT,
  "tax_amount": actual GST/VAT only (CGST + SGST + IGST combined), or null if none,
  "total_amount": the FINAL payable amount including all taxes and rounding,
  "expense_category": one of {list(EXPENSE_CATEGORIES)},
  "summary": one plain-English sentence, under 120 characters, naming what was bought
             and from whom — this is used for search, so make it specific,
  "line_items": [
    {{{{ "description": str, "quantity": str, "unit": str or null,
       "rate": str, "amount": str }}}}
  ],
  "notes": anything important that does not fit above (payment terms, vehicle number,
           meter number, period covered), or null
}}}}

Rules:
- doc_type mapping: a tax invoice, GST invoice or sales invoice is "invoice".
  An electricity, water, phone, internet or any other utility bill is "bill".
  Proof that a payment was made is "receipt". A completion or work certificate
  is "certificate". Everything else (delivery challan, quotation, bank
  statement) is "other".
- Every charge on the document appears EXACTLY ONCE: either as a line item or
  inside "tax_amount" — never in both places.
- "tax_amount" holds actual GST/VAT only. Statutory duties, cesses,
  surcharges, fixed charges and late fees are NOT tax — they are line items.
  On an electricity bill, energy charges, fixed charges AND electricity duty
  are all line items; such a bill usually has no GST and tax_amount is null.
- The arithmetic must close: line items sum to "subtotal", and "subtotal" +
  "tax_amount" equals "total_amount" apart from a printed round-off of paise.
- Amounts: plain decimal strings, no currency symbol and no thousands separators.
  "Rs. 1,84,500.00" becomes "184500.00". Keep two decimal places.
- If a value is genuinely not on the document, use null. Never guess and never
  invent a value to fill a field.
- "vendor_name" is the issuer, NOT the customer the document is addressed to.
- For an electricity or utility bill the vendor is the utility company and
  expense_category is "utilities".
- Return the JSON object only. No commentary, no markdown fences.
"""
