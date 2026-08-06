"""Money maths. All of it happens here, in Decimal — never in the LLM.

Gemini proposes quantities and rates; every amount, tax figure and total on a
printed document is computed by this module so the arithmetic is auditable and
always adds up.
"""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

TWO_PLACES = Decimal("0.01")

_NULLISH = {"", "n/a", "na", "none", "null", "-", "nil", "not stated", "not available"}
_CURRENCY_JUNK = ("₹", "rs.", "rs", "inr", ",", " ", "/-")

_ONES = (
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
)
_TENS = ("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")


def q2(value) -> Decimal:
    """Round to paise, half-up — the convention on Indian invoices."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def parse_decimal(value) -> Decimal | None:
    """'Rs. 1,84,500.00' -> Decimal('184500.00'). None when it isn't a number.

    Both the LLM and uploaded documents hand us money as loose text, so every
    string-to-Decimal conversion in the app goes through here.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return q2(value)
    text = str(value).strip().lower()
    if text in _NULLISH:
        return None
    for junk in _CURRENCY_JUNK:
        text = text.replace(junk, "")
    try:
        return q2(text)
    except (InvalidOperation, ArithmeticError, ValueError):
        return None


def line_amount(quantity, rate) -> Decimal:
    return q2(Decimal(str(quantity)) * Decimal(str(rate)))


def compute_totals(lines: list[dict]) -> dict:
    """Total up priced lines and split GST into CGST/SGST per rate band.

    Each line needs `amount` and `tax_rate`. Returns the quotation-level
    figures plus `tax_groups`, which is what the HSN summary table prints.
    """
    subtotal = q2(sum((line["amount"] for line in lines), Decimal(0)))

    taxable_by_rate: dict[Decimal, Decimal] = {}
    for line in lines:
        rate = q2(line["tax_rate"])
        taxable_by_rate[rate] = taxable_by_rate.get(rate, Decimal(0)) + line["amount"]

    tax_groups = []
    for rate in sorted(taxable_by_rate):
        taxable = q2(taxable_by_rate[rate])
        tax = q2(taxable * rate / 100)
        # Halve then subtract, so CGST + SGST always equals tax exactly.
        cgst = q2(tax / 2)
        tax_groups.append({
            "rate": rate,
            "taxable": taxable,
            "cgst_rate": q2(rate / 2),
            "cgst": cgst,
            "sgst_rate": q2(rate / 2),
            "sgst": tax - cgst,
            "tax": tax,
        })

    gst_amount = q2(sum((group["tax"] for group in tax_groups), Decimal(0)))
    total = q2(subtotal + gst_amount)
    # Blended rate, so a mixed-rate quotation still has one honest number.
    effective_rate = q2(gst_amount / subtotal * 100) if subtotal else Decimal("0.00")

    return {
        "subtotal": subtotal,
        "tax_groups": tax_groups,
        "cgst_total": q2(sum((g["cgst"] for g in tax_groups), Decimal(0))),
        "sgst_total": q2(sum((g["sgst"] for g in tax_groups), Decimal(0))),
        "gst_amount": gst_amount,
        "gst_rate": effective_rate,
        "total": total,
    }


def hsn_summary(lines: list[dict]) -> list[dict]:
    """HSN/SAC-wise tax table — the block every GST document prints at the
    bottom. Groups lines by (code, rate)."""
    buckets: dict[tuple[str, Decimal], Decimal] = {}
    for line in lines:
        key = (line.get("hsn_sac") or "-", q2(line["tax_rate"]))
        buckets[key] = buckets.get(key, Decimal(0)) + line["amount"]

    rows = []
    for (code, rate), taxable_raw in sorted(buckets.items()):
        taxable = q2(taxable_raw)
        tax = q2(taxable * rate / 100)
        cgst = q2(tax / 2)
        rows.append({
            "hsn_sac": code,
            "rate": rate,
            "taxable": taxable,
            "cgst_rate": q2(rate / 2),
            "cgst": cgst,
            "sgst_rate": q2(rate / 2),
            "sgst": tax - cgst,
            "tax": tax,
        })
    return rows


def _below_thousand(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()
    return (_ONES[n // 100] + " Hundred" + (" " + _below_thousand(n % 100) if n % 100 else "")).strip()


def _indian_words(n: int) -> str:
    if n == 0:
        return "Zero"
    parts = []
    for divisor, label in ((10_000_000, "Crore"), (100_000, "Lakh"), (1_000, "Thousand")):
        if n >= divisor:
            parts.append(f"{_indian_words(n // divisor)} {label}")
            n %= divisor
    if n:
        parts.append(_below_thousand(n))
    return " ".join(parts)


def amount_in_words(amount) -> str:
    """Decimal('117988.20') -> 'Rupees One Lakh Seventeen Thousand Nine Hundred
    Eighty Eight and Twenty Paise Only'."""
    value = q2(amount)
    rupees = int(value)
    paise = int((value - rupees) * 100)
    words = f"Rupees {_indian_words(rupees)}"
    if paise:
        words += f" and {_indian_words(paise)} Paise"
    return words + " Only"


def format_inr(value) -> str:
    """1234567.5 -> '12,34,567.50' (Indian digit grouping)."""
    if value is None:
        return ""
    amount = q2(value)
    sign = "-" if amount < 0 else ""
    whole, _, decimals = f"{abs(amount):.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            head, group = head[:-2], head[-2:]
            groups.insert(0, group)
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return f"{sign}{whole}.{decimals}"
