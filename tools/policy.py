"""Policy engine. Pure Python — the LLM never gets to decide policy outcomes."""
from datetime import datetime

MAX_BLAST_RADIUS = 100          # POL-CHG-001: max customers per change record
PROTECTED_VLANS = {100, 150, 200, 300}
ROLES_CAN_REQUEST = {"engineer", "approver", "admin"}
ROLES_CAN_APPROVE = {"approver", "admin"}

# Window: Sunday 02:00-04:00 local (POL-CHG-001)
WINDOW_DAY = 6          # Monday=0 ... Sunday=6
WINDOW_START_H = 2
WINDOW_END_H = 4


def window_is_open(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    return now.weekday() == WINDOW_DAY and WINDOW_START_H <= now.hour < WINDOW_END_H


def check_policies(intent: dict, affected_customers: int, role: str,
                   simulate_window: bool, now: datetime | None = None) -> dict:
    """Run every policy check. Returns {"checks": [...], "passed": bool}."""
    checks = []
    now = now or datetime.now()

    # 1. RBAC — may this role request a change?
    rbac_ok = role in ROLES_CAN_REQUEST
    checks.append({
        "name": "RBAC — requester role",
        "passed": rbac_ok,
        "severity": "hard",
        "detail": (f"Role '{role}' may request changes."
                   if rbac_ok else
                   f"Role '{role}' is not allowed to request network changes."),
    })

    # 2. Maintenance window
    window_required = bool(intent.get("maintenance_window_required", True))
    is_emergency = intent.get("urgency") == "emergency"
    window_ok = window_is_open(now) or simulate_window
    if not window_required:
        checks.append({
            "name": "Maintenance window (POL-CHG-001)",
            "passed": True,
            "severity": "hard",
            "detail": "Not required — change classified as non-service-affecting/diagnostic.",
        })
    elif is_emergency:
        checks.append({
            "name": "Maintenance window (POL-CHG-001)",
            "passed": True,
            "severity": "hard",
            "detail": "Emergency change — window requirement waived per policy §2 "
                      "(requires on-call incident manager sign-off, recorded in audit).",
        })
    else:
        checks.append({
            "name": "Maintenance window (POL-CHG-001)",
            "passed": window_ok,
            "severity": "hard",
            "detail": ("Window is ACTIVE" + (" (simulated for demo)" if simulate_window and not window_is_open(now) else "") + "."
                       if window_ok else
                       f"Current time {now:%A %H:%M} is OUTSIDE the approved window "
                       "(Sunday 02:00–04:00). Service-affecting changes are prohibited outside "
                       "the window unless declared an emergency."),
        })

    # 3. Blast radius
    blast_ok = affected_customers <= MAX_BLAST_RADIUS
    checks.append({
        "name": f"Blast radius (max {MAX_BLAST_RADIUS} customers)",
        "passed": blast_ok,
        "severity": "hard",
        "detail": (f"{affected_customers} customers affected — within limit."
                   if blast_ok else
                   f"{affected_customers} customers affected — exceeds the "
                   f"{MAX_BLAST_RADIUS}-customer limit. Split into multiple change records."),
    })

    # 4. Production VLAN protection
    op = (intent.get("operation") or "").lower()
    vlan = intent.get("vlan")
    destructive_ops = {"delete_vlan", "remove_vlan"}
    prot_ok = not (op in destructive_ops and vlan in PROTECTED_VLANS)
    checks.append({
        "name": "Production VLAN protection (STD-NET-003)",
        "passed": prot_ok,
        "severity": "hard",
        "detail": ("No destructive operation against a protected production VLAN."
                   if prot_ok else
                   f"VLAN {vlan} is a protected production VLAN (100/150/200/300). "
                   "Deletion requires Architecture sign-off and is blocked here."),
    })

    # 5. Human approval gate (informational — always enforced by the UI)
    checks.append({
        "name": "Human approval gate",
        "passed": True,
        "severity": "info",
        "detail": "Execution is impossible without an explicit human Approve "
                  f"(roles allowed to approve: {', '.join(sorted(ROLES_CAN_APPROVE))}).",
    })

    passed = all(c["passed"] for c in checks if c["severity"] == "hard")
    return {"checks": checks, "passed": passed}


def can_approve(role: str) -> bool:
    return role in ROLES_CAN_APPROVE
