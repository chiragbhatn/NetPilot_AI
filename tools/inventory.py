"""Mock NetBox inventory tool. Deterministic — no LLM."""
import json
from functools import lru_cache

from config import DATA_DIR


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads((DATA_DIR / "netbox.json").read_text(encoding="utf-8"))


def all_devices() -> list[dict]:
    return _load()["devices"]


def get_device(name: str):
    name = (name or "").strip().upper()
    for d in _load()["devices"]:
        if d["name"].upper() == name:
            return d
    return None


def get_vlan(vlan_id) -> dict | None:
    try:
        vlan_id = int(vlan_id)
    except (TypeError, ValueError):
        return None
    for v in _load()["vlans"]:
        if v["id"] == vlan_id:
            return v
    return None


def vlan_exists(vlan_id) -> bool:
    return get_vlan(vlan_id) is not None


def all_vlans() -> list[dict]:
    return _load()["vlans"]


def get_customers(device: str | None = None, tier: str | None = None,
                  vlan: int | None = None) -> list[dict]:
    out = _load()["customers"]
    if device:
        out = [c for c in out if c["device"].upper() == device.strip().upper()]
    if tier:
        out = [c for c in out if c["tier"].lower() == tier.strip().lower()]
    if vlan is not None:
        out = [c for c in out if c["vlan"] == int(vlan)]
    return out


def get_topology() -> dict:
    return _load()["topology"]


def get_interfaces(device: str) -> list[dict]:
    return _load()["interfaces"].get((device or "").strip().upper(), [])


def query_inventory(query: dict) -> dict:
    """Single dispatch entry point used by the Tool Selection Agent's output.

    Supported query types:
      {"type": "device", "name": "OLT-12"}
      {"type": "vlan", "vlan_id": 220}
      {"type": "all_vlans"}
      {"type": "customers", "device": "OLT-12", "tier": "Premium", "vlan": 200}
      {"type": "topology"}
      {"type": "interfaces", "device": "SW-01"}
    """
    qtype = (query.get("type") or "").lower()
    if qtype == "device":
        dev = get_device(query.get("name", ""))
        if not dev:
            return {"found": False, "error": f"Device '{query.get('name')}' not found in inventory"}
        return {"found": True, "device": dev, "interfaces": get_interfaces(dev["name"])}
    if qtype == "vlan":
        v = get_vlan(query.get("vlan_id"))
        if not v:
            return {"found": False,
                    "error": f"VLAN {query.get('vlan_id')} does not exist in the network inventory",
                    "known_vlans": [x["id"] for x in all_vlans()]}
        return {"found": True, "vlan": v}
    if qtype == "all_vlans":
        return {"found": True, "vlans": all_vlans()}
    if qtype == "customers":
        cust = get_customers(query.get("device"), query.get("tier"), query.get("vlan"))
        sample = cust[:5]
        return {"found": True, "count": len(cust), "sample": sample,
                "tiers": sorted({c["tier"] for c in cust})}
    if qtype == "topology":
        return {"found": True, "topology": get_topology()}
    if qtype == "interfaces":
        return {"found": True, "device": query.get("device"),
                "interfaces": get_interfaces(query.get("device", ""))}
    return {"found": False, "error": f"Unknown inventory query type '{qtype}'"}
