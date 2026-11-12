"""Configuration read from the environment. Secrets never live in the code."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes")


# Branding (single place to rename the app)
APP_NAME = os.getenv("APP_NAME", "El Vecino que Sabe")

# LLM: any OpenAI-compatible API (Groq by default)
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1500"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
MAX_AGENT_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "4"))

# Database: if DATABASE_URL is empty, data is read from the JSON files (handy for tests)
DATABASE_URL = os.getenv("DATABASE_URL", "")
SEED_ON_START = _bool(os.getenv("SEED_ON_START", "true"))

ALLOWED_ORIGINS = _list(
    os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
)

# BDNS client. TLS certificate validation remains enabled by httpx defaults.
BDNS_API_BASE_URL = os.getenv(
    "BDNS_API_BASE_URL", "https://www.infosubvenciones.es/bdnstrans/api"
)
BDNS_PORTAL_ID = os.getenv("BDNS_PORTAL_ID", "GE")
BDNS_TIMEOUT_SECONDS = float(os.getenv("BDNS_TIMEOUT_SECONDS", "30"))
BDNS_MIN_REQUEST_INTERVAL_SECONDS = float(
    os.getenv("BDNS_MIN_REQUEST_INTERVAL_SECONDS", "1")
)
BDNS_CACHE_TTL_SECONDS = float(os.getenv("BDNS_CACHE_TTL_SECONDS", "300"))
BDNS_MAX_RETRIES = int(os.getenv("BDNS_MAX_RETRIES", "2"))
BDNS_MAX_PAGE_SIZE = int(os.getenv("BDNS_MAX_PAGE_SIZE", "100"))
BDNS_DOCUMENT_MAX_BYTES = int(os.getenv("BDNS_DOCUMENT_MAX_BYTES", str(25 * 1024 * 1024)))
BDNS_DOCUMENT_STORAGE_DIR = os.getenv(
    "BDNS_DOCUMENT_STORAGE_DIR",
    str(Path(__file__).resolve().parents[2] / "storage" / "bdns"),
)
BDNS_LINK_CHECK_INTERVAL_SECONDS = float(os.getenv("BDNS_LINK_CHECK_INTERVAL_SECONDS", "1"))
# Internal review API is disabled until a private bearer token is configured.
BDNS_REVIEW_TOKEN = os.getenv("BDNS_REVIEW_TOKEN", "")
