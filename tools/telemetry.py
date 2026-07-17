"""Mock telemetry tool. Deterministic — no LLM."""
import json
from functools import lru_cache

from config import DATA_DIR


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads((DATA_DIR / "telemetry.json").read_text(encoding="utf-8"))


def query_telemetry(query: dict) -> dict:
    """{"device": "OLT-12"} -> live-looking stats for that device."""
    device = (query.get("device") or "").strip().upper()
    data = _load().get(device)
    if not data:
        return {"found": False, "error": f"No telemetry for device '{device}'",
                "known_devices": list(_load().keys())}
    return {"found": True, "device": device, "telemetry": data}


def all_telemetry() -> dict:
    return _load()
