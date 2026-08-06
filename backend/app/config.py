"""App settings loaded from the repo-root .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at the repo root; resolve it relative to this file so the app
# works no matter which directory uvicorn or scripts are launched from.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    DATABASE_URL: str
    GEMINI_API_KEY: str = ""
    CHROMA_PATH: str = "./.chroma"
    FRONTEND_ORIGIN: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
