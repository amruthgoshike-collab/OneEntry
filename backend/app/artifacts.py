"""Shared plumbing for generated PDF artifacts.

Quotations, invoices and certificates all print the same company header and
all file their PDFs the same way, so both live here rather than being copied
into each router.
"""
from datetime import date
from pathlib import Path

from app.config import STORAGE_ROOT, get_settings


def company_context() -> dict:
    """The issuing business, printed at the top of every document.

    Single-tenant demo — there is no company table, so this comes from config.
    """
    settings = get_settings()
    return {
        "name": settings.COMPANY_NAME,
        "address": settings.COMPANY_ADDRESS,
        "gstin": settings.COMPANY_GSTIN,
        "state": settings.COMPANY_STATE,
        "phone": settings.COMPANY_PHONE,
        "email": settings.COMPANY_EMAIL,
        "bank_name": settings.COMPANY_BANK_NAME,
        "bank_account": settings.COMPANY_BANK_ACCOUNT,
        "bank_ifsc": settings.COMPANY_BANK_IFSC,
    }


def artifact_path(number: str) -> Path:
    """backend/storage/generated/YYYY/MM/QTN-0001.pdf"""
    today = date.today()
    return STORAGE_ROOT / "generated" / f"{today:%Y}" / f"{today:%m}" / f"{number}.pdf"
