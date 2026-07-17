"""Mock post-change verification tool."""
import time


def verify_change(intent: dict, affected_count: int, progress_cb=None) -> dict:
    """Simulated post-change checks (mirrors SOP-NET-019 checklist)."""
    vlan = intent.get("vlan", "?")
    checks = [
        {"name": "ONU / port status", "passed": True,
         "detail": f"{affected_count}/{affected_count} migrated ONUs online"},
        {"name": "VLAN membership", "passed": True,
         "detail": f"All {affected_count} service-ports report user-vlan {vlan}"},
        {"name": f"DHCP relay on VLAN {vlan}", "passed": True,
         "detail": f"Test client obtained a lease in 4 s via relay 10.20.0.10 "
                   "(hard gate added after INC-2419)"},
        {"name": "Gateway reachability", "passed": True,
         "detail": f"Ping to VLAN {vlan} gateway: {affected_count}/{affected_count} test probes OK"},
        {"name": "Traffic baseline", "passed": True,
         "detail": "Uplink traffic within 4% of pre-change baseline after observation period"},
    ]
    for i, c in enumerate(checks, start=1):
        if progress_cb:
            progress_cb(i, len(checks), f"Verifying: {c['name']}")
        time.sleep(0.4)
    return {"passed": all(c["passed"] for c in checks), "checks": checks}
