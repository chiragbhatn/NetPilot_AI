"""SQLite audit trail. Every terminal outcome (blocked / rejected / executed) is logged."""
import json
import sqlite3
from datetime import datetime

from config import AUDIT_DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    user_role TEXT,
    request_text TEXT,
    intent_json TEXT,
    risk_score INTEGER,
    risk_level TEXT,
    reviewer_verdict TEXT,
    decision TEXT,            -- executed | blocked | rejected | failed
    blocked_stage TEXT,
    approver TEXT,
    reject_reason TEXT,
    generated_cli TEXT,
    execution_json TEXT,
    verification_json TEXT,
    executive_summary TEXT
);
"""


def _conn():
    conn = sqlite3.connect(AUDIT_DB_PATH)
    conn.execute(_SCHEMA)
    return conn


def log_entry(**kw) -> int:
    """Insert one audit row; unknown values may be None."""
    row = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "user_role": kw.get("user_role"),
        "request_text": kw.get("request_text"),
        "intent_json": json.dumps(kw.get("intent"), default=str) if kw.get("intent") else None,
        "risk_score": kw.get("risk_score"),
        "risk_level": kw.get("risk_level"),
        "reviewer_verdict": kw.get("reviewer_verdict"),
        "decision": kw.get("decision"),
        "blocked_stage": kw.get("blocked_stage"),
        "approver": kw.get("approver"),
        "reject_reason": kw.get("reject_reason"),
        "generated_cli": kw.get("generated_cli"),
        "execution_json": json.dumps(kw.get("execution"), default=str) if kw.get("execution") else None,
        "verification_json": json.dumps(kw.get("verification"), default=str) if kw.get("verification") else None,
        "executive_summary": kw.get("executive_summary"),
    }
    with _conn() as conn:
        cur = conn.execute(
            f"INSERT INTO audit_log ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
            list(row.values()),
        )
        return cur.lastrowid


def fetch_all(limit: int = 50) -> list[dict]:
    with _conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
