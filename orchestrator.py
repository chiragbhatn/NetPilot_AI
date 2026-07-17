"""NetPilot AI orchestrator.

Phase 1 (run_analysis):  Intent -> Plan -> Tool selection -> Evidence -> Validation
                          -> Policy -> Risk -> Reviewer debate -> Explanation
Phase 2 (run_execution): CLI generation -> blocklist scan -> mock execution -> verification
Phase 2 only runs after an explicit human approval in the UI. Every terminal outcome
(blocked / rejected / executed) is written to the SQLite audit log.
"""
import traceback

from agents import (explainer_agent, intent_agent, planner_agent, reviewer_agent,
                    risk_agent, summary_agent, tool_selector_agent)
from guardrails.cli_blocklist import scan_cli
from guardrails.sanitizer import sanitize
from rag import store as rag_store
from tools import audit, execution, inventory, policy, telemetry, verification

STAGE_ORDER = ["intent", "plan", "evidence", "policy", "risk", "debate", "explanation"]

DHCP_TIER_OPS = {"vlan_migration", "vlan_change", "config_change", "delete_vlan"}


def _level_for(score: int) -> str:
    """Deterministic score->level banding; the LLM's own label can drift."""
    return ("Low" if score < 25 else "Medium" if score < 50
            else "High" if score < 75 else "Critical")


def _tier_from_text(text: str | None) -> str | None:
    text = (text or "").lower()
    for tier in ("premium", "enterprise", "residential"):
        if tier in text:
            return tier.capitalize()
    return None


def _affected_customers(intent: dict) -> list[dict]:
    op = (intent.get("operation") or "").lower()
    device = intent.get("device")
    tier = _tier_from_text(intent.get("target_customers"))
    if op in {"diagnostic", "other"}:
        return []
    if op in {"delete_vlan", "remove_vlan"} and intent.get("vlan"):
        return inventory.get_customers(vlan=intent["vlan"])
    if op in {"reboot", "reload"} and device:
        return inventory.get_customers(device=device)
    if device:
        return inventory.get_customers(device=device, tier=tier)
    return []


def _evidence_digest(ev: dict, impact: dict) -> dict:
    """Compact, truncated evidence bundle fed to the LLM agents."""
    def cap(s, n=900):
        s = str(s)
        return s if len(s) <= n else s[:n] + " ...[truncated]"

    return {
        "inventory_lookups": [{"query": e["query"], "result": cap(e["result"])}
                              for e in ev["inventory"]],
        "telemetry": [{"query": e["query"], "result": cap(e["result"])}
                      for e in ev["telemetry"]],
        "knowledge_snippets": [
            {"source": r["source"], "title": r["title"], "snippet": cap(r["snippet"], 1100)}
            for e in ev["knowledge"] for r in e["results"]
        ],
        "computed_impact": impact,
    }


def run_analysis(user_text: str, role: str, simulate_window: bool, progress=None) -> dict:
    """Phase 1. Returns a state dict; never raises (errors land in state)."""
    def note(stage, msg):
        if progress:
            progress(stage, msg)

    state = {
        "request_text": user_text,
        "role": role,
        "simulate_window": simulate_window,
        "stages": {k: {"status": "pending"} for k in STAGE_ORDER},
        "blocked": False,
        "blocked_stage": None,
        "blocked_reason": None,
        "error": None,
        "impact": {},
        "analysis_complete": False,
        "decision": None,          # set later: executed | blocked | rejected
        "audit_id": None,
    }
    stages = state["stages"]

    clean = sanitize(user_text)
    state["warnings"] = clean["warnings"]
    text = clean["text"]
    if not text:
        state["error"] = "Empty request."
        return state

    try:
        # ---- 1. Intent -------------------------------------------------
        note("intent", "🧭 Parsing intent...")
        intent = intent_agent.parse_intent(text).model_dump()
        stages["intent"] = {"status": "done", "data": intent}

        # Self-description: "what can you do / what VLANs do we have / who can approve"
        # is answered straight from the platform's own inventory and policy engine —
        # deterministic, always accurate, no further LLM calls.
        if (intent.get("operation") or "").lower() == "help":
            state["help"] = _build_help()
            for k in STAGE_ORDER[1:]:
                stages[k]["status"] = "skipped"
            state["analysis_complete"] = True
            state["decision"] = "help"
            return state

        # Off-topic gate: NetPilot is a change platform, not a chatbot. Anything that
        # isn't a network operation stops here — no planning, no evidence, no LLM spend.
        if (intent.get("operation") or "other").lower() == "other":
            stages["intent"]["status"] = "blocked"
            _block(state, "intent",
                   "This is not a network operation. NetPilot only processes network change "
                   "requests and diagnostics (e.g. VLAN migrations, config changes, device "
                   "health questions). Nothing was planned or executed. Tip: ask "
                   "'what can you do?' to see the platform's capabilities.")
            state["stages"]["explanation"] = {"status": "skipped"}
            state["analysis_complete"] = True
            _audit_terminal(state, decision="blocked",
                            summary_text="Request rejected at the intent stage: not a network "
                                         "operation (off-topic / conversational input). No plan "
                                         "was generated and no tools were invoked.")
            return state

        # ---- 2. Plan ---------------------------------------------------
        note("plan", "🗺️ Drafting execution plan...")
        plan = planner_agent.make_plan(intent_agent.Intent(**intent)).model_dump()
        stages["plan"] = {"status": "done", "data": plan}

        # ---- 3. Tool selection + evidence gathering --------------------
        note("evidence", "🔎 Tool Selection Agent choosing evidence sources...")
        selection = tool_selector_agent.select_tools(
            intent_agent.Intent(**intent), plan["summary"]).model_dump()

        ev = {"inventory": [], "telemetry": [], "knowledge": []}
        for call in selection["calls"]:
            tool_name, query = call["tool"], call["query"]
            note("evidence", f"🔎 {tool_name}: {query}")
            if tool_name == "inventory" and isinstance(query, dict):
                ev["inventory"].append({"query": query, "reason": call.get("reason", ""),
                                        "result": inventory.query_inventory(query)})
            elif tool_name == "telemetry":
                q = query if isinstance(query, dict) else {"device": str(query)}
                ev["telemetry"].append({"query": q, "reason": call.get("reason", ""),
                                        "result": telemetry.query_telemetry(q)})
            elif tool_name == "knowledge":
                q = query if isinstance(query, str) else str(query)
                ev["knowledge"].append({"query": q, "reason": call.get("reason", ""),
                                        "results": rag_store.retrieve(q, k=3)})

        # Safety nets. The orchestrator validates the target VLAN deterministically below,
        # so that lookup is recorded as evidence even when the agent didn't request it —
        # otherwise the Risk Agent rightly treats the VLAN's L3 services as unverified.
        if intent.get("vlan") is not None and not any(
                isinstance(e["query"], dict) and e["query"].get("type") == "vlan"
                and str(e["query"].get("vlan_id")) == str(intent["vlan"])
                for e in ev["inventory"]):
            q = {"type": "vlan", "vlan_id": intent["vlan"]}
            ev["inventory"].append({"query": q,
                                    "reason": "orchestrator validation (VLAN existence + L3 services)",
                                    "result": inventory.query_inventory(q)})

        # The reviewer needs incident context even if the agent skipped knowledge queries.
        if not ev["knowledge"]:
            q = f"{intent.get('operation')} VLAN {intent.get('vlan')} incident SOP"
            ev["knowledge"].append({"query": q, "reason": "fallback (agent selected no knowledge query)",
                                    "results": rag_store.retrieve(q, k=3)})

        # Deterministic validation of targets against inventory
        validation = {"passed": True, "problems": []}
        if intent.get("device") and not inventory.get_device(intent["device"]):
            validation["passed"] = False
            validation["problems"].append(
                f"Device '{intent['device']}' does not exist in inventory.")
        if intent.get("vlan") is not None and not inventory.vlan_exists(intent["vlan"]):
            known = [v["id"] for v in inventory.all_vlans()]
            validation["passed"] = False
            validation["problems"].append(
                f"VLAN {intent['vlan']} does not exist anywhere in the network "
                f"(provisioned VLANs: {known}). Per STD-NET-003 a VLAN may only be used if it "
                "exists in NetBox and on every device in the traffic path.")

        affected = _affected_customers(intent)
        state["impact"] = {
            "affected_customers": len(affected),
            "tiers": sorted({c["tier"] for c in affected}),
            "customer_ids": [c["id"] for c in affected],
        }
        state["_affected_list"] = affected  # full records, used for CLI generation

        stages["evidence"] = {"status": "done" if validation["passed"] else "blocked",
                              "tool_calls": selection["calls"], "evidence": ev,
                              "validation": validation}

        if not validation["passed"]:
            _block(state, "evidence", " ".join(validation["problems"]))
            _explain_blocked(state, note)
            _audit_terminal(state, decision="blocked")
            return state

        # ---- 4. Policy (deterministic) ----------------------------------
        note("policy", "📏 Running policy checks...")
        pol = policy.check_policies(intent, len(affected), role, simulate_window)
        stages["policy"] = {"status": "done" if pol["passed"] else "blocked", **pol}
        if not pol["passed"]:
            failed = [c for c in pol["checks"] if not c["passed"]]
            _block(state, "policy", " | ".join(c["detail"] for c in failed))
            _explain_blocked(state, note)
            _audit_terminal(state, decision="blocked")
            return state

        # ---- 5. Risk -----------------------------------------------------
        note("risk", "⚖️ Risk Agent scoring the change...")
        digest = _evidence_digest(ev, state["impact"])
        # The Risk Agent scores on technical evidence only (inventory + telemetry).
        # Institutional memory (RAG incidents/SOPs) belongs to the Reviewer — this keeps
        # the debate genuine: the reviewer can escalate citing history the scorer never saw.
        risk_digest = {k: v for k, v in digest.items() if k != "knowledge_snippets"}
        risk = risk_agent.assess_risk(intent, plan, risk_digest).model_dump()
        # Recompute the total ourselves — small models fumble their own arithmetic.
        risk["risk_score"] = max(0, min(100, risk["base_score"]
                                        + sum(a["points"] for a in risk["adders"])))
        risk["risk_level"] = _level_for(risk["risk_score"])
        stages["risk"] = {"status": "done", "data": risk}

        # ---- 6. Reviewer debate -------------------------------------------
        note("debate", "🕵️ Change Reviewer critiquing the plan...")
        review = reviewer_agent.review_change(intent, plan, risk, digest).model_dump()
        review["adjusted_risk_level"] = _level_for(review["adjusted_risk_score"])
        stages["debate"] = {
            "status": "blocked" if review["verdict"] == "reject" else "done",
            "reviewer": review,
            "final_risk_level": review["adjusted_risk_level"],
            "final_risk_score": review["adjusted_risk_score"],
            "risk_changed": (review["adjusted_risk_level"] != risk["risk_level"]
                             or review["adjusted_risk_score"] >= risk["risk_score"] + 5),
        }
        if review["verdict"] == "reject":
            _block(state, "debate", f"Change Reviewer rejected the plan: {review['critique']}")

        # ---- 7. Explanation -----------------------------------------------
        note("explanation", "📝 Explanation Agent writing the decision report...")
        context = {
            "request_text": text,
            "intent": intent,
            "plan": plan,
            "evidence": digest,
            "policy_checks": pol["checks"],
            "initial_risk": risk,
            "reviewer": review,
            "blocked": state["blocked"],
            "blocked_reason": state["blocked_reason"],
        }
        exp = explainer_agent.explain(context).model_dump()
        stages["explanation"] = {"status": "done", "data": exp}

        if state["blocked"]:
            _audit_terminal(state, decision="blocked")
        state["analysis_complete"] = True
        return state

    except Exception as e:  # graceful degradation — the UI shows a friendly card
        state["error"] = f"{type(e).__name__}: {e}"
        state["error_detail"] = traceback.format_exc(limit=3)
        for k, v in stages.items():
            if v.get("status") == "pending":
                v["status"] = "skipped"
        return state


def _build_help() -> dict:
    """Platform self-description, built from live inventory + policy constants."""
    customers = inventory.get_customers()
    by_tier = {}
    for c in customers:
        by_tier.setdefault(c["tier"], {"count": 0, "devices": set()})
        by_tier[c["tier"]]["count"] += 1
        by_tier[c["tier"]]["devices"].add(c["device"])
    return {
        "what_i_do": [
            "Plan network changes from plain English (VLAN migrations, config changes, "
            "reboots, diagnostics) — I am a change-review board, not a chatbot.",
            "Gather my own evidence: an agent decides which inventory, telemetry, and "
            "knowledge-base (SOPs + past incidents) queries to run.",
            "Enforce policy in code: maintenance window, RBAC, blast radius, protected VLANs.",
            "Score risk, then have a second skeptical AI reviewer critique the plan — "
            "it can raise risk or reject outright.",
            "Explain every decision with cited evidence, then wait for a human to approve "
            "before (mock) execution, verification, and audit logging.",
        ],
        "devices": [{"Device": d["name"], "Vendor": d["vendor"], "Model": d["model"],
                     "Role": d["role"], "Status": d["status"]}
                    for d in inventory.all_devices()],
        "vlans": [{"VLAN": v["id"], "Name": v["name"], "Purpose": v["purpose"],
                   "DHCP relay": v.get("dhcp_relay") or "—"}
                  for v in inventory.all_vlans()],
        "customer_summary": {tier: {"count": info["count"],
                                    "devices": sorted(info["devices"])}
                             for tier, info in sorted(by_tier.items())},
        "roles": {
            "engineer": "Can submit change requests and diagnostics. Cannot approve — "
                        "the Approve button is locked in code.",
            "approver": "Everything an engineer can do, plus approve or reject changes "
                        "at the human gate.",
            "admin": "Same approval rights as approver (not exposed in the demo UI).",
        },
        "policies": [
            f"Maintenance window: Sunday {policy.WINDOW_START_H:02d}:00–"
            f"{policy.WINDOW_END_H:02d}:00 for service-affecting changes "
            "(demo toggle in the sidebar simulates it being active).",
            f"Blast radius: max {policy.MAX_BLAST_RADIUS} customers per change.",
            f"Protected production VLANs (no deletion): "
            f"{', '.join(str(v) for v in sorted(policy.PROTECTED_VLANS))}.",
            "Forbidden commands (reload, erase, production 'no vlan', ...) are scanned "
            "out of generated CLI before execution.",
            "Every terminal outcome — executed, blocked, or rejected — is written to the "
            "SQLite audit log with an executive summary.",
        ],
        "try_these": [
            "Migrate all premium customers on OLT-12 to VLAN 220 during tonight's "
            "maintenance window.  (full pipeline + AI debate)",
            "Move the premium customers on OLT-12 over to VLAN 999 tonight.  "
            "(blocks — VLAN doesn't exist)",
            "Delete VLAN 200 on SW-01 immediately.  (blocks — protected VLAN)",
            "Why is the uplink utilization on OLT-12 so high?  (diagnostic)",
            "Reboot OLT-12 right now.  (watch the reviewer and CLI guardrails react)",
        ],
    }


def _block(state: dict, stage: str, reason: str) -> None:
    state["blocked"] = True
    state["blocked_stage"] = stage
    state["blocked_reason"] = reason
    for k in STAGE_ORDER[STAGE_ORDER.index(stage) + 1:]:
        if k != "explanation":
            state["stages"][k]["status"] = "skipped"


def _explain_blocked(state: dict, note) -> None:
    """Even a blocked pipeline gets a grounded explanation report."""
    try:
        note("explanation", "📝 Explaining why the change was blocked...")
        stg = state["stages"]
        context = {
            "request_text": state["request_text"],
            "intent": stg["intent"].get("data"),
            "plan": stg["plan"].get("data"),
            "blocked": True,
            "blocked_at_stage": state["blocked_stage"],
            "blocked_reason": state["blocked_reason"],
            "validation": stg["evidence"].get("validation"),
            "policy_checks": stg.get("policy", {}).get("checks"),
        }
        exp = explainer_agent.explain(context).model_dump()
        state["stages"]["explanation"] = {"status": "done", "data": exp}
    except Exception:
        state["stages"]["explanation"] = {"status": "skipped"}
    state["analysis_complete"] = True


def _audit_terminal(state: dict, decision: str, approver: str | None = None,
                    reject_reason: str | None = None, exec_state: dict | None = None,
                    summary_text: str | None = None) -> None:
    """Write one audit row for a terminal outcome."""
    stg = state["stages"]
    intent = stg["intent"].get("data")
    debate = stg.get("debate", {})
    risk = stg.get("risk", {}).get("data", {})
    summary = summary_text or summary_agent.summarize({
        "request_text": state["request_text"],
        "intent": intent,
        "outcome": decision,
        "blocked_stage": state.get("blocked_stage"),
        "blocked_reason": state.get("blocked_reason"),
        "reject_reason": reject_reason,
        "final_risk": debate.get("final_risk_level") or risk.get("risk_level"),
        "reviewer_verdict": (debate.get("reviewer") or {}).get("verdict"),
        "execution": (exec_state or {}).get("execution"),
        "verification": (exec_state or {}).get("verification"),
    })
    state["decision"] = decision
    state["audit_id"] = audit.log_entry(
        user_role=state["role"],
        request_text=state["request_text"],
        intent=intent,
        risk_score=debate.get("final_risk_score") or risk.get("risk_score"),
        risk_level=debate.get("final_risk_level") or risk.get("risk_level"),
        reviewer_verdict=(debate.get("reviewer") or {}).get("verdict"),
        decision=decision,
        blocked_stage=state.get("blocked_stage"),
        approver=approver,
        reject_reason=reject_reason,
        generated_cli="\n".join((exec_state or {}).get("cli_bundle", {}).get("cli", [])) or None,
        execution=(exec_state or {}).get("execution"),
        verification=(exec_state or {}).get("verification"),
        executive_summary=summary,
    )
    state["executive_summary"] = summary


def log_rejection(state: dict, approver: str, reason: str) -> None:
    _audit_terminal(state, decision="rejected", approver=approver, reject_reason=reason)


def run_execution(state: dict, approver: str, progress=None) -> dict:
    """Phase 2 — only callable after human approval. Returns exec_state."""
    intent = state["stages"]["intent"]["data"]
    affected = state.get("_affected_list", [])
    exec_state = {"status": "running", "cli_bundle": None, "scan": None,
                  "execution": None, "verification": None}

    cli_bundle = execution.generate_cli(intent, affected)
    exec_state["cli_bundle"] = cli_bundle

    scan = scan_cli(cli_bundle["cli"])
    exec_state["scan"] = scan
    if scan["blocked"]:
        exec_state["status"] = "blocked"
        state["blocked"] = True
        state["blocked_stage"] = "execution"
        state["blocked_reason"] = ("Forbidden command(s) in generated CLI: "
                                   + "; ".join(f"`{v['command']}` — {v['reason']}"
                                               for v in scan["violations"]))
        _audit_terminal(state, decision="blocked", approver=approver, exec_state=exec_state)
        return exec_state

    exec_state["execution"] = execution.execute(cli_bundle, progress_cb=progress)
    exec_state["verification"] = verification.verify_change(
        intent, len(affected), progress_cb=progress)
    exec_state["status"] = "done"
    _audit_terminal(state, decision="executed", approver=approver, exec_state=exec_state)
    return exec_state
