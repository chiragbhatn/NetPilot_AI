"""Mock execution tool: generates vendor-realistic CLI and simulates running it."""
import time
from datetime import datetime

from tools import inventory


def generate_cli(intent: dict, affected_customers: list[dict]) -> dict:
    """Deterministic CLI generation from validated intent. Returns
    {"device", "vendor", "cli": [...], "rollback_cli": [...]}."""
    device_name = (intent.get("device") or "OLT-12").upper()
    device = inventory.get_device(device_name) or {"vendor": "Huawei", "name": device_name,
                                                   "mgmt_ip": "10.10.1.22"}
    vendor = device.get("vendor", "Huawei")
    op = (intent.get("operation") or "").lower()
    vlan = intent.get("vlan")
    old_vlans = sorted({c["vlan"] for c in affected_customers}) or [200]
    old_vlan = old_vlans[0]
    ts = datetime.now().strftime("%Y%m%d")
    n = len(affected_customers)

    cli: list[str] = []
    rollback: list[str] = []

    if vendor == "Huawei" and op in {"vlan_migration", "vlan_change", "config_change"} and vlan:
        cli = [
            f"backup configuration tftp 10.10.0.50 {device['name']}_{ts}_pre.cfg",
            f"vlan {vlan} smart",
            f"port vlan {vlan} 0/19 0",
        ]
        for c in affected_customers[:2]:
            sp = 1100 + int(c["id"].split("-")[1]) % 900
            cli += [
                f"undo service-port {sp}",
                f"service-port {sp} vlan {vlan} gpon {c['port']} ont 1 gemport 1 "
                f"multi-service user-vlan {vlan} tag-transform translate",
            ]
        if n > 2:
            cli.append(f"# ... service-port migration repeated for the remaining {n - 2} "
                       f"ONUs (batched, max 20 per batch per SOP-NET-014) ...")
        cli.append("save")
        rollback = [
            f"# Restore from {device['name']}_{ts}_pre.cfg",
            f"# Re-create all {n} service-ports with user-vlan {old_vlan}",
            f"service-port <id> vlan {old_vlan} gpon <port> ont 1 gemport 1 "
            f"multi-service user-vlan {old_vlan} tag-transform translate",
            "save",
        ]
    elif vendor == "Cisco" and op in {"vlan_migration", "vlan_change", "config_change"} and vlan:
        cli = [
            f"copy running-config tftp://10.10.0.50/{device['name']}_{ts}_pre.cfg",
            "configure terminal",
            f"vlan {vlan}",
            f" name AUTO-{vlan}",
            "interface range Gi1/0/1 - 24",
            f" switchport access vlan {vlan}",
            "end",
            "write memory",
        ]
        rollback = [
            f"configure replace tftp://10.10.0.50/{device['name']}_{ts}_pre.cfg force",
        ]
    elif op in {"delete_vlan", "remove_vlan"} and vlan:
        if vendor == "Cisco":
            cli = [
                f"copy running-config tftp://10.10.0.50/{device['name']}_{ts}_pre.cfg",
                "configure terminal",
                f"no vlan {vlan}",
                "end",
                "write memory",
            ]
        else:
            cli = [
                f"backup configuration tftp 10.10.0.50 {device['name']}_{ts}_pre.cfg",
                f"undo vlan {vlan}",
                "save",
            ]
        rollback = [f"# Restore from {device['name']}_{ts}_pre.cfg"]
    elif op in {"reboot", "reload"}:
        cli = ["reload" if vendor == "Cisco" else "reboot"]
        rollback = ["# Device restart cannot be rolled back — power-on recovery only"]
    else:
        cli = [
            f"# No CLI template for operation '{op}' — generic config session",
            f"backup configuration tftp 10.10.0.50 {device['name']}_{ts}_pre.cfg",
        ]
        rollback = [f"# Restore from {device['name']}_{ts}_pre.cfg"]

    return {"device": device["name"], "vendor": vendor, "mgmt_ip": device.get("mgmt_ip"),
            "cli": cli, "rollback_cli": rollback}


EXEC_STAGES = [
    ("Connecting to {device} ({ip}) over SSH", 0.6),
    ("Authenticating with TACACS+ service account", 0.5),
    ("Taking pre-change configuration backup", 0.9),
    ("Applying VLAN / uplink configuration", 0.8),
    ("Migrating service-ports in batches of 20", 1.2),
    ("Saving configuration", 0.6),
    ("Closing session", 0.3),
]


def execute(cli_bundle: dict, progress_cb=None) -> dict:
    """Simulate execution with staged delays. progress_cb(step_index, total, message)."""
    start = time.time()
    total = len(EXEC_STAGES)
    log = []
    for i, (msg, delay) in enumerate(EXEC_STAGES, start=1):
        message = msg.format(device=cli_bundle["device"], ip=cli_bundle.get("mgmt_ip", "?"))
        if progress_cb:
            progress_cb(i, total, message)
        time.sleep(delay)
        log.append(f"[{datetime.now():%H:%M:%S}] {message} ... OK")
    duration = round(time.time() - start, 1)
    return {"success": True, "duration_sec": duration, "log": log,
            "executed_at": datetime.now().isoformat(timespec="seconds"),
            "cli": cli_bundle["cli"]}
