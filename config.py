"""Central configuration: paths, environment, OpenAI client."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
KNOWLEDGE_DIR = ROOT / "knowledge"
DB_DIR = ROOT / "db"
DB_DIR.mkdir(exist_ok=True)

# Load .env from the project folder first, then fall back to the parent folder.
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

AUDIT_DB_PATH = DB_DIR / "netpilot_audit.db"
CHROMA_PATH = DB_DIR / "chroma"

_client = None


def api_key_present() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def get_client():
    """Lazily build a single OpenAI client."""
    global _client
    if _client is None:
        from openai import OpenAI

        if not api_key_present():
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        _client = OpenAI()
    return _client
