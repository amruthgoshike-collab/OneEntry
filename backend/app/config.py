"""App settings loaded from the repo-root .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
# .env lives at the repo root; resolve it relative to this file so the app
# works no matter which directory uvicorn or scripts are launched from.
ENV_FILE = BACKEND_DIR.parent / ".env"

# Uploaded documents land in backend/storage/YYYY/MM/ (gitignored).
STORAGE_ROOT = BACKEND_DIR / "storage"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    DATABASE_URL: str
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    CHROMA_PATH: str = "./.chroma"
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # Printed at the top of every generated document. There is no company
    # table — this is a single-tenant demo, so it lives in config.
    COMPANY_NAME: str = "Sridhar Constructions & Interiors"
    COMPANY_ADDRESS: str = "Plot 14, Road No. 3, Kukatpally, Hyderabad - 500072"
    COMPANY_GSTIN: str = "36AACCS8842K1ZP"
    COMPANY_STATE: str = "Telangana (36)"
    COMPANY_PHONE: str = "+91 90300 11220"
    COMPANY_EMAIL: str = "works@sridharconstructions.example"
    QUOTATION_VALIDITY_DAYS: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
