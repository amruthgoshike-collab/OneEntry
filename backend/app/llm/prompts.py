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
