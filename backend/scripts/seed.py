"""Wipe and rebuild a demo dataset: 6 customers, 12 jobs across six months.

Everything goes through `app.services`, the same functions the API routers
call, so seeded records carry real lineage — sequential QTN/INV/CERT numbers,
`quotation_id` on every invoice, line items copied rather than re-entered, and
an event trail on every job. The only thing skipped is Gemini: line items and
scope paragraphs are fixtures here, so a reset is fast and the totals are
predictable.

**Destructive.** Every entity, job, quotation, invoice, certificate, document
and event is deleted first so the script is idempotent.

    cd backend && python -m scripts.seed
"""
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.db import SessionLocal
from app.events import log_event
from app.models import (
    Certificate,
    Document,
    Entity,
    Invoice,
    Job,
    JobEvent,
    LineItem,
    Quotation,
)
from app.numbering import next_number
from app.services import build_certificate, build_invoice, build_quotation

TODAY = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)

CUSTOMERS = [
    ("Sai Ram Constructions", "36AAACS4821P1ZK", "9848012345",
     "accounts@sairamconstructions.example", "8-2-120, Road No. 2, Banjara Hills, Hyderabad - 500034"),
    ("Vaishnavi Infra Projects", "36AABCV7734L1ZQ", "9866123456",
     "projects@vaishnaviinfra.example", "Plot 41, Silicon Valley, Madhapur, Hyderabad - 500081"),
    ("Meghana Builders & Developers", "36AACCM2298R1ZB", "9701234567",
     "info@meghanabuilders.example", "H.No. 3-6-14, Himayatnagar, Hyderabad - 500029"),
    ("Sri Chaitanya Enterprises", "36AADCS9012J1ZF", "9885567890",
     "srichaitanya.ent@example.com", "Shop 12, Kukatpally Housing Board, Hyderabad - 500072"),
    ("Nakshatra Realty LLP", "36AAEFN5567M1ZD", "9963345678",
     "works@nakshatrarealty.example", "Survey 88, Nanakramguda, Hyderabad - 500032"),
    ("Pragathi Engineering Works", "36AAGFP3341N1ZY", "9848998877",
     "pragathi.works@example.com", "Plot 7, IDA Uppal, Hyderabad - 500039"),
]

# Base line items per trade, priced for a nominal quantity. Each job scales
# these. A "lumpsum" line scales its rate instead of its quantity, so nobody
# ends up quoting 0.6 of a lumpsum.
TRADES = {
    "interior_painting": [
        ("Surface preparation including scraping, wire brushing and sanding", "995473", 1000, "sqft", "4.50"),
        ("Acrylic wall putty application - 2 coats with level sanding", "995473", 1000, "sqft", "15.00"),
        ("Interior wall primer - 1 coat", "995473", 1000, "sqft", "7.50"),
        ("Asian Paints Royale Luxury Emulsion - 2 coats finish", "995473", 1000, "sqft", "28.00"),
    ],
    "electrical_wiring": [
        ("Concealed conduit and FR copper wiring for light points", "995461", 60, "nos", "950.00"),
        ("16A power point wiring with modular switch and socket", "995461", 18, "nos", "1450.00"),
        ("Distribution board with MCB and RCCB protection", "8537", 2, "nos", "12500.00"),
        ("Earthing pit with copper plate and chemical compound", "995461", 1, "nos", "8500.00"),
    ],
    "false_ceiling": [
        ("Gypsum board false ceiling on GI perimeter framework", "995465", 500, "sqft", "145.00"),
        ("Cove lighting groove with plywood backing", "995465", 60, "rft", "210.00"),
        ("Ceiling putty and emulsion paint - 2 coats", "995473", 500, "sqft", "22.00"),
    ],
    "plumbing": [
        ("CPVC hot and cold water supply line with fittings", "995463", 1, "lumpsum", "48000.00"),
        ("UPVC soil, waste and rainwater drainage lines", "995463", 1, "lumpsum", "26000.00"),
        ("Sanitary fixture installation - WC, basin and fittings", "995463", 12, "nos", "1200.00"),
    ],
    "ms_fabrication": [
        ("MS handrail fabrication and erection with 40mm box section", "7308", 180, "rft", "1250.00"),
        ("MS staircase stringer and tread framework", "7308", 1, "lumpsum", "68000.00"),
        ("Red oxide primer and synthetic enamel finish on MS work", "995473", 180, "rft", "145.00"),
    ],
    "waterproofing": [
        ("Terrace surface preparation and crack filling with polymer mortar", "995473", 1200, "sqft", "12.00"),
        ("APP modified bitumen membrane waterproofing - 3mm", "995473", 1200, "sqft", "38.00"),
        ("Protective screed 25mm with wire mesh reinforcement", "995473", 1200, "sqft", "18.00"),
    ],
}

# (customer index, trade, scale, title, site, description, days ago, state)
#   quoted      -> quotation only
#   unpaid      -> quotation approved, invoice raised, not yet paid
#   paid        -> invoice settled, work under way
#   certified   -> completed and certificate issued
JOBS = [
    (0, "ms_fabrication", "2.15", "MS railing and staircase fabrication - clubhouse",
     "Nanakramguda", "Handrails for 3 floors plus staircase framework, red oxide and enamel finish",
     176, "certified"),
    (1, "interior_painting", "3.0", "Office interior painting - 3000 sqft",
     "Gachibowli", "Interior painting of 3rd floor office, 2 coats Asian Paints Royale over putty",
     162, "certified"),
    (2, "waterproofing", "1.4", "Terrace waterproofing - 1680 sqft",
     "Himayatnagar", "APP membrane waterproofing over terrace slab with protective screed",
     148, "paid"),
    (3, "electrical_wiring", "3.4", "Electrical wiring - 4 BHK duplex",
     "Kukatpally", "Complete concealed wiring, DBs, earthing and modular fittings for duplex villa",
     131, "certified"),
    (0, "false_ceiling", "2.4", "Gypsum false ceiling - showroom",
     "Banjara Hills", "Grid and gypsum ceiling with cove lighting for ground floor showroom",
     117, "paid"),
    (4, "plumbing", "1.8", "Plumbing and sanitary - 6 flats",
     "Manikonda", "CPVC supply, UPVC drainage and sanitary fixture installation across 6 units",
     103, "paid"),
    (5, "ms_fabrication", "1.0", "MS fabrication - factory mezzanine railing",
     "IDA Uppal", "Mezzanine handrail and access stair framework at the Uppal unit",
     88, "unpaid"),
    (1, "electrical_wiring", "1.0", "Electrical wiring - site office",
     "Madhapur", "Wiring, DB and earthing for temporary site office and stores",
     71, "unpaid"),
    (2, "interior_painting", "1.5", "Interior repainting - 1500 sqft flat",
     "Kondapur", "Repainting of 3 BHK flat including putty touch-up and 2 coats emulsion",
     54, "unpaid"),
    (4, "false_ceiling", "0.75", "False ceiling - reception area",
     "Jubilee Hills", "Gypsum ceiling with cove lighting for reception and waiting area",
     38, "quoted"),
    (3, "plumbing", "0.6", "Plumbing rework - 2 BHK",
     "Miyapur", "Replacement of leaking CPVC lines and refitting of sanitary ware",
     21, "quoted"),
    (5, "waterproofing", "0.5", "Bathroom waterproofing - 3 units",
     "LB Nagar", "Sunken bathroom waterproofing with crack filling and protective screed",
     9, "quoted"),
]

SCOPE_SUMMARIES = {
    "ms_fabrication": (
        "The mild steel handrail and staircase framework at the {site} site was fabricated "
        "and erected in full for {customer}. The executed scope comprised 40mm box section "
        "handrails across all floors along with the staircase stringer and tread framework. "
        "All fabricated surfaces were treated with red oxide primer followed by a synthetic "
        "enamel finish. The work was completed and handed over on {completed}."
    ),
    "interior_painting": (
        "The interior painting work at the {site} site was completed for {customer}. "
        "Surface preparation was carried out by scraping, wire brushing and sanding, "
        "followed by two coats of acrylic wall putty with level sanding and one coat of "
        "interior primer. Two coats of Asian Paints Royale Luxury Emulsion were applied to "
        "achieve the specified finish. The premises were cleaned and handed over on {completed}."
    ),
    "electrical_wiring": (
        "The electrical installation at the {site} site was completed for {customer}. "
        "Concealed conduit with FR copper wiring was laid for all light and power points, "
        "and modular switches and sockets were fitted throughout. Distribution boards with "
        "MCB and RCCB protection were installed along with a copper plate earthing pit. "
        "The installation was tested and handed over on {completed}."
    ),
}


def wipe(db) -> None:
    """Delete in FK-safe order so a re-run starts from an empty schema."""
    counts = {}
    for model in (JobEvent, LineItem, Certificate, Invoice, Quotation, Document, Job, Entity):
        counts[model.__tablename__] = db.execute(
            select(func.count()).select_from(model)
        ).scalar_one()
        db.query(model).delete(synchronize_session=False)
    db.commit()
    removed = {table: n for table, n in counts.items() if n}
    print("Wiped: " + (", ".join(f"{n} {t}" for t, n in removed.items()) if removed
                       else "nothing (database was already empty)"))


def scaled_lines(trade: str, scale: Decimal) -> list[dict]:
    lines = []
    for description, hsn_sac, quantity, unit, rate in TRADES[trade]:
        if unit == "lumpsum":
            qty, unit_rate = Decimal(1), Decimal(rate) * scale
        else:
            qty, unit_rate = Decimal(quantity) * scale, Decimal(rate)
        lines.append({
            "description": description,
            "hsn_sac": hsn_sac,
            "quantity": qty.quantize(Decimal("0.01")),
            "unit": unit,
            "rate": unit_rate.quantize(Decimal("0.01")),
            "tax_rate": Decimal("18"),
        })
    return lines


def main() -> int:
    with SessionLocal() as db:
        wipe(db)

        entities = []
        for index, (name, gstin, phone, email, address) in enumerate(CUSTOMERS):
            entity = Entity(
                name=name, type="customer", gstin=gstin, phone=phone,
                email=email, address=address,
                created_at=TODAY - timedelta(days=200 - index * 3),
            )
            db.add(entity)
            entities.append(entity)
        db.flush()
        print(f"Created {len(entities)} customers")

        rows = []
        for (cust, trade, scale, title, site, description, days_ago, state) in JOBS:
            customer = entities[cust]
            created = TODAY - timedelta(days=days_ago)

            job = Job(
                job_number=next_number(db, Job.job_number, "JOB"),
                customer_id=customer.id,
                title=title,
                description=description,
                site_address=f"{site}, Hyderabad",
                status="enquiry",
                created_at=created,
            )
            db.add(job)
            db.flush()
            job.customer  # noqa: B018 — services render the customer block
            log_event(db, job.id, "job_created",
                      f"{job.job_number} created for {customer.name}", at=created)

            quoted_at = created + timedelta(days=2)
            quotation = build_quotation(
                db, job, scaled_lines(trade, Decimal(scale)), as_of=quoted_at
            )
            db.flush()

            invoice = certificate = None
            if state != "quoted":
                approved_at = quoted_at + timedelta(days=6)
                invoice = build_invoice(db, quotation, as_of=approved_at)
                db.flush()

            if state in ("paid", "certified"):
                paid_at = invoice.created_at + timedelta(days=11)
                invoice.status = "paid"
                log_event(db, job.id, "invoice_paid",
                          f"{invoice.invoice_number} settled in full, {invoice.total}",
                          at=paid_at)
                previous, job.status = job.status, "in_progress"
                log_event(db, job.id, "status_changed",
                          f"{previous} -> {job.status}", at=paid_at)

            if state == "certified":
                done_at = invoice.created_at + timedelta(days=26)
                job.completed_on = done_at.date()
                previous, job.status = job.status, "completed"
                log_event(db, job.id, "status_changed",
                          f"{previous} -> {job.status}", at=done_at)
                db.flush()
                certificate = build_certificate(
                    db,
                    job,
                    SCOPE_SUMMARIES[trade].format(
                        site=site, customer=customer.name,
                        completed=f"{job.completed_on:%d %B %Y}",
                    ),
                    as_of=done_at + timedelta(days=1),
                )

            rows.append((job, quotation, invoice, certificate, state))

        db.commit()

        print(f"Created {len(rows)} jobs\n")
        header = f"{'JOB':<9} {'CUSTOMER':<30} {'TOTAL':>12}  {'STATUS':<12} {'ARTIFACTS'}"
        print(header)
        print("-" * len(header))
        for job, quotation, invoice, certificate, state in rows:
            artifacts = [quotation.quotation_number]
            if invoice:
                artifacts.append(f"{invoice.invoice_number} ({invoice.status})")
            if certificate:
                artifacts.append(certificate.certificate_number)
            print(f"{job.job_number:<9} {job.customer.name[:29]:<30} "
                  f"{quotation.total:>12,} {job.status:<12} {' / '.join(artifacts)}")

        totals = [q.total for _, q, _, _, _ in rows]
        print(f"\nValue range: {min(totals):,} to {max(totals):,}")
        print(f"Events written: {db.execute(select(func.count()).select_from(JobEvent)).scalar_one()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
