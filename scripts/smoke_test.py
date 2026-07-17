"""Headless end-to-end smoke test of the full pipeline (uses the real OpenAI API).

Usage: python scripts/smoke_test.py [happy|vlan999|window|all]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import run_analysis, run_execution  # noqa: E402
from rag.store import ingest  # noqa: E402

HAPPY = "Migrate all premium customers on OLT-12 to VLAN 220 during tonight's maintenance window."
VLAN999 = "Move the premium customers on OLT-12 over to VLAN 999 tonight."


def show(state: dict) -> None:
    print(f"\n{'=' * 70}")
    print(f"REQUEST: {state['request_text']}")
    for k, v in state["stages"].items():
        print(f"  [{v.get('status', '?'):8}] {k}")
    if state.get("error"):
        print(f"  ERROR: {state['error']}")
        print(state.get("error_detail", ""))
    if state["blocked"]:
        print(f"  BLOCKED at {state['blocked_stage']}: {state['blocked_reason'][:200]}")
    dbg = state["stages"].get("debate", {})
    if dbg.get("reviewer"):
        r = dbg["reviewer"]
        init = state["stages"]["risk"]["data"]
        print(f"  Initial risk: {init['risk_level']} ({init['risk_score']}) -> "
              f"Reviewer: {r['adjusted_risk_level']} ({r['adjusted_risk_score']}), "
              f"verdict={r['verdict']}")
        print(f"  Reviewer cites: {r['evidence_cited'][:2]}")
    exp = state["stages"].get("explanation", {}).get("data")
    if exp:
        print(f"  Decision: {exp['decision']}")
    print(f"  Audit id: {state.get('audit_id')}")


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    print("Ingesting knowledge base...")
    print(f"  {ingest()} chunks ready")

    def progress(stage, msg):
        print(f"    .. {msg}")

    if which in ("happy", "all"):
        state = run_analysis(HAPPY, role="approver", simulate_window=True, progress=progress)
        show(state)
        if state["analysis_complete"] and not state["blocked"] and not state.get("error"):
            print("  Approving + executing...")
            ex = run_execution(state, approver="approver",
                               progress=lambda i, n, m: print(f"    [{i}/{n}] {m}"))
            print(f"  Execution: {ex['status']}, "
                  f"verification passed: {ex.get('verification', {}).get('passed')}")
            print(f"  CLI sample: {json.dumps(ex['cli_bundle']['cli'][:4], indent=2)}")

    if which in ("vlan999", "all"):
        state = run_analysis(VLAN999, role="engineer", simulate_window=True, progress=progress)
        show(state)
        assert state["blocked"] and state["blocked_stage"] == "evidence", \
            "VLAN 999 should block at evidence stage"

    if which in ("window", "all"):
        state = run_analysis(HAPPY, role="engineer", simulate_window=False, progress=progress)
        show(state)
        assert state["blocked"] and state["blocked_stage"] == "policy", \
            "Outside window should block at policy stage"

    print("\nSmoke test finished.")


if __name__ == "__main__":
    main()
