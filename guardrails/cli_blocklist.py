"""Forbidden-command scanner. Runs on generated CLI *before* execution."""
import re

# (pattern, human explanation)
FORBIDDEN = [
    (r"^\s*erase\s+startup-config", "Erases device startup configuration — catastrophic."),
    (r"^\s*write\s+erase", "Wipes stored configuration — catastrophic."),
    (r"^\s*reload\b", "Full device reload — mass outage for every customer on the device."),
    (r"^\s*reboot\b", "Full device reboot — mass outage for every customer on the device."),
    (r"^\s*format\s+(flash|disk)", "Destroys device filesystem."),
    (r"^\s*no\s+vlan\s+(100|150|200|300)\b", "Deletes a protected production VLAN (STD-NET-003)."),
    (r"^\s*undo\s+vlan\s+(100|150|200|300)\b", "Deletes a protected production VLAN (STD-NET-003)."),
    (r"^\s*delete\s+/force", "Forced file deletion on device storage."),
    (r"^\s*shutdown\s*$", "Blind interface shutdown without scoping is not allowed."),
]


def scan_cli(cli_lines: list[str]) -> dict:
    """Returns {"blocked": bool, "violations": [{"line", "command", "reason"}]}."""
    violations = []
    for idx, line in enumerate(cli_lines, start=1):
        for pat, reason in FORBIDDEN:
            if re.search(pat, line, flags=re.IGNORECASE):
                violations.append({"line": idx, "command": line.strip(), "reason": reason})
                break
    return {"blocked": bool(violations), "violations": violations}
