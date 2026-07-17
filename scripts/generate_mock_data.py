"""Regenerates data/netbox.json and data/telemetry.json deterministically.

Run once at project setup: python scripts/generate_mock_data.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

FIRST = ["Aarav", "Meera", "Rohan", "Priya", "Kabir", "Ananya", "Vikram", "Isha",
         "Dev", "Tara", "Arjun", "Nisha", "Sameer", "Pooja", "Rahul", "Sneha",
         "Aditya", "Kavya", "Manish", "Ritu", "Nikhil", "Divya", "Suresh", "Lata",
         "Farhan", "Zoya"]
LAST = ["Sharma", "Verma", "Iyer", "Khan", "Patel", "Reddy", "Nair", "Gupta",
        "Mehta", "Bose", "Joshi", "Kulkarni", "Das"]
BUSINESSES = ["Apex Logistics Pvt Ltd", "BlueRiver Diagnostics", "Cortex Software Labs",
              "Dhruv Textiles", "Everline BPO Services", "Falcon Securities"]


def person(i: int) -> str:
    return f"{FIRST[i % len(FIRST)]} {LAST[(i * 7) % len(LAST)]}"


def main() -> None:
    customers = []
    cid = 1000

    # 52 Premium customers on OLT-12 (the happy-path migration target), currently on VLAN 200
    for i in range(52):
        cid += 1
        customers.append({
            "id": f"CUST-{cid}",
            "name": person(i),
            "tier": "Premium",
            "device": "OLT-12",
            "port": f"0/{(i // 16) + 1}/{i % 16}",
            "onu": f"ONU-12-{i + 1:03d}",
            "vlan": 200,
            "service": "FTTH Premium 300 Mbps",
        })

    # 8 Premium customers on OLT-01
    for i in range(8):
        cid += 1
        customers.append({
            "id": f"CUST-{cid}",
            "name": person(i + 52),
            "tier": "Premium",
            "device": "OLT-01",
            "port": f"0/1/{i}",
            "onu": f"ONU-01-{i + 1:03d}",
            "vlan": 200,
            "service": "FTTH Premium 300 Mbps",
        })

    # 6 Enterprise customers on SW-01 (VLAN 300)
    for i, biz in enumerate(BUSINESSES):
        cid += 1
        customers.append({
            "id": f"CUST-{cid}",
            "name": biz,
            "tier": "Enterprise",
            "device": "SW-01",
            "port": f"Gi1/0/{i + 1}",
            "onu": None,
            "vlan": 300,
            "service": "Dedicated Internet 1 Gbps",
        })

    # 30 Residential customers spread across OLT-01 / OLT-12 (VLAN 100)
    for i in range(30):
        cid += 1
        dev = "OLT-01" if i % 2 == 0 else "OLT-12"
        customers.append({
            "id": f"CUST-{cid}",
            "name": person(i + 11),
            "tier": "Residential",
            "device": dev,
            "port": f"0/{(i // 10) + 4}/{i % 10}",
            "onu": f"ONU-{dev[-2:]}-R{i + 1:03d}",
            "vlan": 100,
            "service": "FTTH Home 100 Mbps",
        })

    netbox = {
        "devices": [
            {"name": "OLT-01", "vendor": "Huawei", "model": "MA5800-X7", "role": "olt",
             "site": "POP-North", "mgmt_ip": "10.10.1.11", "status": "active",
             "software": "V800R021C10", "uplink_to": "SW-01"},
            {"name": "OLT-12", "vendor": "Huawei", "model": "MA5800-X17", "role": "olt",
             "site": "POP-East", "mgmt_ip": "10.10.1.22", "status": "active",
             "software": "V800R021C10", "uplink_to": "SW-01"},
            {"name": "SW-01", "vendor": "Cisco", "model": "Catalyst 9300-48T", "role": "aggregation",
             "site": "DC-Core", "mgmt_ip": "10.10.0.2", "status": "active",
             "software": "IOS-XE 17.9.4", "uplink_to": "RTR-01"},
            {"name": "RTR-01", "vendor": "Cisco", "model": "ASR-9901", "role": "core-router",
             "site": "DC-Core", "mgmt_ip": "10.10.0.1", "status": "active",
             "software": "IOS-XR 7.9.2", "uplink_to": "INTERNET"},
        ],
        "interfaces": {
            "OLT-01": [{"name": "0/19/0", "type": "10GE uplink", "to": "SW-01 Te1/1/1", "status": "up"}],
            "OLT-12": [{"name": "0/19/0", "type": "10GE uplink", "to": "SW-01 Te1/1/2", "status": "up"},
                        {"name": "0/19/1", "type": "10GE uplink (standby)", "to": "SW-01 Te1/1/3", "status": "up"}],
            "SW-01": [{"name": "Te1/1/1", "type": "10GE", "to": "OLT-01 0/19/0", "status": "up"},
                       {"name": "Te1/1/2", "type": "10GE", "to": "OLT-12 0/19/0", "status": "up"},
                       {"name": "Te1/1/3", "type": "10GE", "to": "OLT-12 0/19/1", "status": "up"},
                       {"name": "Fo1/1/1", "type": "40GE uplink", "to": "RTR-01 Hu0/0/0/1", "status": "up"}],
            "RTR-01": [{"name": "Hu0/0/0/1", "type": "40GE", "to": "SW-01 Fo1/1/1", "status": "up"},
                        {"name": "Hu0/0/0/0", "type": "100GE transit", "to": "Upstream ISP", "status": "up"}],
        },
        "vlans": [
            {"id": 100, "name": "RES-DATA", "purpose": "Residential internet", "status": "active",
             "svi": "SW-01 Vlan100", "dhcp_relay": "10.20.0.10"},
            {"id": 150, "name": "RES-VOICE", "purpose": "Residential voice", "status": "active",
             "svi": "SW-01 Vlan150", "dhcp_relay": "10.20.0.10"},
            {"id": 200, "name": "PREMIUM-DATA", "purpose": "Premium internet (legacy)", "status": "active",
             "svi": "SW-01 Vlan200", "dhcp_relay": "10.20.0.10"},
            {"id": 220, "name": "PREMIUM-DATA-NEW", "purpose": "Premium internet (new segment)", "status": "active",
             "svi": "SW-01 Vlan220", "dhcp_relay": "10.20.0.10",
             "note": "DHCP relay added 2026-06-15 after incident INC-2419"},
            {"id": 300, "name": "ENT-DATA", "purpose": "Enterprise dedicated internet", "status": "active",
             "svi": "RTR-01 BVI300", "dhcp_relay": None},
            {"id": 400, "name": "MGMT", "purpose": "Device management", "status": "active",
             "svi": "SW-01 Vlan400", "dhcp_relay": None},
        ],
        "topology": {
            "layers": ["Access (OLT-01, OLT-12)", "Aggregation (SW-01)", "Core (RTR-01)", "Internet"],
            "links": [
                {"a": "OLT-01", "b": "SW-01"},
                {"a": "OLT-12", "b": "SW-01"},
                {"a": "SW-01", "b": "RTR-01"},
                {"a": "RTR-01", "b": "INTERNET"},
            ],
        },
        "customers": customers,
    }

    telemetry = {
        "OLT-01": {"cpu_pct": 34, "mem_pct": 41, "uplink_utilization_pct": 47,
                    "uptime_days": 389, "onu_total": 46, "onu_online": 46,
                    "temperature_c": 41, "alarms": []},
        "OLT-12": {"cpu_pct": 61, "mem_pct": 58, "uplink_utilization_pct": 83,
                    "uptime_days": 212, "onu_total": 214, "onu_online": 211,
                    "temperature_c": 47,
                    "alarms": [{"severity": "minor", "message": "Uplink 0/19/0 utilization above 80% for 6h"},
                                {"severity": "warning", "message": "3 ONUs offline > 24h (suspected power)"}]},
        "SW-01": {"cpu_pct": 22, "mem_pct": 37, "uplink_utilization_pct": 52,
                   "uptime_days": 512, "onu_total": None, "onu_online": None,
                   "temperature_c": 39, "alarms": []},
        "RTR-01": {"cpu_pct": 18, "mem_pct": 44, "uplink_utilization_pct": 38,
                    "uptime_days": 730, "onu_total": None, "onu_online": None,
                    "temperature_c": 36, "alarms": []},
    }

    (DATA / "netbox.json").write_text(json.dumps(netbox, indent=2), encoding="utf-8")
    (DATA / "telemetry.json").write_text(json.dumps(telemetry, indent=2), encoding="utf-8")
    print(f"Wrote netbox.json ({len(customers)} customers) and telemetry.json")


if __name__ == "__main__":
    sys.exit(main())
