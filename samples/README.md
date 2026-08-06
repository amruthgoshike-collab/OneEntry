# samples/

Documents used by `backend/tests/test_extract.py` to smoke-test Gemini extraction.

**These three files are synthetic placeholders**, generated to exercise the
pipeline because this folder was empty. The businesses in them are invented.
Replace them with real bills — the point of this folder is to test extraction
against messy real-world documents (phone photos, skewed scans, faded thermal
receipts), which is where synthetic samples flatter the model.

Each one targets a different failure mode:

| file | exercises |
|---|---|
| `sunrise-hardware-tax-invoice.png` | GST invoice, line-item table, CGST/SGST split, round-off |
| `metro-power-electricity-bill.pdf` | PDF path, due date, and a decoy "after due date" amount |
| `sri-laxmi-transport-receipt.jpg` | JPEG artifacts, rotation, no GST, amount written in words |
