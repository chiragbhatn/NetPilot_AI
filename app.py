"""NetPilot AI — Explainable Agentic Network Operations Platform (Streamlit UI)."""
import json

import pandas as pd
import streamlit as st

st.set_page_config(page_title="NetPilot AI", page_icon="🛰️", layout="wide",
                   initial_sidebar_state="expanded")

import config  # noqa: E402
from orchestrator import STAGE_ORDER, log_rejection, run_analysis, run_execution  # noqa: E402
from tools import audit, policy  # noqa: E402

# ----------------------------------------------------------------------------- styling
st.markdown("""
<style>
.block-container { padding-top: 1.2rem; }
.np-badge { display:inline-block; padding: 2px 12px; border-radius: 12px;
            font-weight: 600; font-size: 0.85rem; color: white; }
.np-low { background:#2e7d32; } .np-medium { background:#ef6c00; }
.np-high { background:#c62828; } .np-critical { background:#6a1b9a; }
.np-planner { background:#e3f2fd; border-left: 5px solid #1565c0; padding: 12px 14px;
              border-radius: 8px; color:#0d2b45; }
.np-reviewer { background:#fff3e0; border-left: 5px solid #ef6c00; padding: 12px 14px;
               border-radius: 8px; color:#4a2c00; }
.np-consensus { background:#e8f5e9; border-left: 5px solid #2e7d32; padding: 12px 14px;
                border-radius: 8px; color:#0f3d17; margin-top: 10px; }
.np-consensus-blocked { background:#ffebee; border-left: 5px solid #c62828; padding: 12px 14px;
                border-radius: 8px; color:#4a0d0d; margin-top: 10px; }
.np-step { padding: 3px 0; }
</style>
""", unsafe_allow_html=True)

STAGE_META = {
    "intent": ("🧭", "Intent"),
    "plan": ("🗺️", "Plan"),
    "evidence": ("🔎", "Evidence"),
    "policy": ("📏", "Policy"),
    "risk": ("⚖️", "Risk"),
    "debate": ("🥊", "AI Debate — Planner vs Reviewer"),
    "explanation": ("📝", "Explanation — Decision Report"),
}
STATUS_ICON = {"done": "✅", "blocked": "⛔", "skipped": "⏭️", "pending": "⏳", "error": "⚠️"}

EXAMPLES = [
    ("✅ Happy path: VLAN 220 migration",
     "Migrate all premium customers on OLT-12 to VLAN 220 during tonight's maintenance window."),
    ("⛔ Nonexistent VLAN 999",
     "Move the premium customers on OLT-12 over to VLAN 999 tonight."),
    ("⛔ Delete a production VLAN",
     "Delete VLAN 200 on SW-01 immediately."),
]


def _init_state():
    defaults = {"pipeline": None, "exec_state": None, "approved_by": None,
                "reject_mode": False, "queued_request": None, "request_text": ""}
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def _reset_run():
    st.session_state.pipeline = None
    st.session_state.exec_state = None
    st.session_state.approved_by = None
    st.session_state.reject_mode = False


def _risk_badge(level: str) -> str:
    cls = {"Low": "np-low", "Medium": "np-medium", "High": "np-high",
           "Critical": "np-critical"}.get(level, "np-medium")
    return f'<span class="np-badge {cls}">{level}</span>'


def render_help(h):
    st.success("ℹ️ **You asked what NetPilot can do — here is the platform describing itself.** "
               "Everything below comes straight from its own inventory and policy engine, "
               "so it is always accurate.")
    st.markdown("#### 🛰️ What I do")
    for b in h["what_i_do"]:
        st.markdown(f"- {b}")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 📦 Devices under management")
        st.dataframe(pd.DataFrame(h["devices"]), hide_index=True, width="stretch")
    with c2:
        st.markdown("#### 🔢 Provisioned VLANs")
        st.dataframe(pd.DataFrame(h["vlans"]), hide_index=True, width="stretch")
    st.markdown("#### 👥 Customers")
    cols = st.columns(max(len(h["customer_summary"]), 1))
    for col, (tier, info) in zip(cols, h["customer_summary"].items()):
        col.metric(tier, info["count"])
        col.caption("on " + ", ".join(info["devices"]))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🧑‍🤝‍🧑 Who can do what")
        for role, desc in h["roles"].items():
            st.markdown(f"- **{role}** — {desc}")
    with c2:
        st.markdown("#### 📏 Policies in force")
        for p in h["policies"]:
            st.markdown(f"- {p}")
    st.markdown("#### 💡 Things to try")
    for t in h["try_these"]:
        st.markdown(f"- `{t}`")


# ----------------------------------------------------------------------------- stage cards
def card(stage_key: str, status: str, expanded: bool = False):
    icon, title = STAGE_META[stage_key]
    return st.expander(f"{icon} {title} — {STATUS_ICON.get(status, '⏳')} {status}",
                       expanded=expanded)


def render_intent(stage):
    with card("intent", stage["status"]):
        d = stage["data"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Operation", d.get("operation") or "—")
        c2.metric("Device", d.get("device") or "—")
        c3.metric("Target VLAN", d.get("vlan") if d.get("vlan") is not None else "—")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Affected:** {d.get('target_customers') or '—'}")
        c2.markdown(f"**Urgency:** {d.get('urgency')}")
        c3.markdown(f"**Window required:** {'Yes' if d.get('maintenance_window_required') else 'No'}")
        st.caption(f"“{d.get('intent')}”")


def render_plan(stage):
    with card("plan", stage["status"]):
        d = stage["data"]
        st.markdown(f"**Planner summary:** {d['summary']}")
        for s in d["steps"]:
            tool = f" &nbsp;`{s['tool']}`" if s.get("tool") else ""
            rb = (f"<br/><small>↩️ rollback: {s['rollback_action']}</small>"
                  if s.get("rollback_action") else "")
            st.markdown(f"<div class='np-step'><b>{s['step_id']}.</b> {s['action']}{tool}{rb}</div>",
                        unsafe_allow_html=True)


def render_evidence(stage, blocked_reason):
    expanded = stage["status"] == "blocked"
    with card("evidence", stage["status"], expanded=expanded):
        st.caption("Tool calls below were chosen by the Tool Selection Agent — not hardcoded.")
        for c in stage.get("tool_calls", []):
            st.markdown(f"- **{c['tool']}** ← `{json.dumps(c['query']) if isinstance(c['query'], dict) else c['query']}`"
                        f"  <small>({c.get('reason', '')})</small>", unsafe_allow_html=True)
        ev = stage.get("evidence", {})
        t1, t2, t3 = st.tabs([f"📦 Inventory ({len(ev.get('inventory', []))})",
                              f"📈 Telemetry ({len(ev.get('telemetry', []))})",
                              f"📚 Knowledge ({sum(len(e['results']) for e in ev.get('knowledge', []))})"])
        with t1:
            for e in ev.get("inventory", []):
                st.markdown(f"**Query:** `{json.dumps(e['query'])}`")
                st.json(e["result"], expanded=False)
        with t2:
            for e in ev.get("telemetry", []):
                st.markdown(f"**Query:** `{json.dumps(e['query'])}`")
                st.json(e["result"], expanded=False)
        with t3:
            for e in ev.get("knowledge", []):
                st.markdown(f"**RAG query:** *{e['query']}*")
                for r in e["results"]:
                    with st.container(border=True):
                        st.markdown(f"**{r['title']}** — `{r['source']}` (distance {r['distance']})")
                        st.markdown(r["snippet"][:600] + ("…" if len(r["snippet"]) > 600 else ""))
        val = stage.get("validation", {})
        if val and not val.get("passed", True):
            st.error("**Inventory validation failed:**\n\n" +
                     "\n".join(f"- {p}" for p in val["problems"]))
        elif val:
            st.success("Inventory validation passed: device and VLAN targets exist.")


def render_policy(stage):
    expanded = stage["status"] == "blocked"
    with card("policy", stage["status"], expanded=expanded):
        for c in stage.get("checks", []):
            icon = "✅" if c["passed"] else "❌"
            tag = "" if c["severity"] == "hard" else " *(informational)*"
            st.markdown(f"{icon} **{c['name']}**{tag} — {c['detail']}")


def render_risk(stage, debate_stage):
    with card("risk", stage["status"]):
        d = stage["data"]
        final_level = (debate_stage or {}).get("final_risk_level") or d["risk_level"]
        final_score = (debate_stage or {}).get("final_risk_score") or d["risk_score"]
        c1, c2 = st.columns([2, 3])
        with c1:
            st.markdown(f"**Initial (Risk Agent):** {_risk_badge(d['risk_level'])} "
                        f"&nbsp;{d['risk_score']}/100", unsafe_allow_html=True)
            if (debate_stage or {}).get("risk_changed"):
                st.markdown(f"**After review:** {_risk_badge(final_level)} "
                            f"&nbsp;{final_score}/100 &nbsp;📈 *raised by the reviewer*",
                            unsafe_allow_html=True)
            else:
                st.markdown(f"**After review:** {_risk_badge(final_level)} &nbsp;{final_score}/100",
                            unsafe_allow_html=True)
            st.progress(min(final_score, 100) / 100)
        with c2:
            st.markdown(f"**Business impact:** {d['business_impact']}")
            st.markdown(f"**Estimated downtime:** {d['estimated_downtime']} · "
                        f"**Confidence:** {d['confidence']:.0%}")
        st.markdown("**Reasons:**")
        for r in d["reasons"]:
            st.markdown(f"- {r}")


def render_debate(stage, plan_stage, risk_stage):
    expanded = stage["status"] == "blocked" or stage.get("risk_changed", False)
    with card("debate", stage["status"], expanded=expanded):
        r = stage["reviewer"]
        init = risk_stage["data"]
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🧠 Planner says")
            st.markdown(f"<div class='np-planner'>{plan_stage['data']['summary']}<br/><br/>"
                        f"Initial risk assessment: <b>{init['risk_level']} "
                        f"({init['risk_score']}/100)</b></div>", unsafe_allow_html=True)
        with col2:
            st.markdown("#### 🕵️ Reviewer says")
            concerns = "".join(f"<li>{c}</li>" for c in r.get("concerns", []))
            st.markdown(f"<div class='np-reviewer'>{r['critique']}"
                        f"<ul>{concerns}</ul>"
                        f"Adjusted risk: <b>{r['adjusted_risk_level']} "
                        f"({r['adjusted_risk_score']}/100)</b> · Verdict: "
                        f"<b>{r['verdict'].upper()}</b></div>", unsafe_allow_html=True)
        if r.get("evidence_cited"):
            st.markdown("**Reviewer's evidence:**")
            for e in r["evidence_cited"]:
                st.markdown(f"> 📚 {e}")
        if r.get("required_modifications"):
            st.markdown("**Required modifications:**")
            for m in r["required_modifications"]:
                st.markdown(f"- 🔧 {m}")
        cls = "np-consensus-blocked" if r["verdict"] == "reject" else "np-consensus"
        st.markdown(f"<div class='{cls}'><b>🤝 Consensus:</b> {r['consensus']}</div>",
                    unsafe_allow_html=True)


def render_explanation(stage):
    with card("explanation", stage["status"], expanded=True):
        d = stage["data"]
        st.markdown(f"### {d['decision']}")
        st.progress(d["confidence"], text=f"Confidence: {d['confidence']:.0%}")
        st.markdown(f"**Reasoning:** {d['reasoning']}")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Evidence cited:**")
            for e in d["evidence_cited"]:
                st.markdown(f"- {e}")
        with c2:
            st.markdown("**Policies checked:**")
            for p in d["policies_checked"]:
                st.markdown(f"- {p}")
        st.markdown(f"**↩️ Rollback:** {d['rollback_summary']}")
        st.markdown(f"**🔬 Verification plan:** {d['verification_plan']}")
        st.info(f"**Recommendation:** {d['recommendation']}")


def render_execution_cards(exec_state):
    scan = exec_state.get("scan") or {}
    status = ("blocked" if exec_state["status"] == "blocked"
              else "done" if exec_state["status"] == "done" else "pending")
    with st.expander(f"⚙️ Execution — {STATUS_ICON.get(status)} {status}",
                     expanded=(status == "blocked")):
        bundle = exec_state["cli_bundle"]
        st.markdown(f"**Device:** {bundle['device']} ({bundle['vendor']}) · "
                    f"mgmt {bundle.get('mgmt_ip', '?')}")
        st.markdown("**Generated CLI** (scanned against the forbidden-command blocklist):")
        st.code("\n".join(bundle["cli"]), language="text")
        if scan.get("blocked"):
            st.error("**⛔ HARD BLOCK — forbidden command(s) detected before execution:**\n\n" +
                     "\n".join(f"- Line {v['line']}: `{v['command']}` — {v['reason']}"
                               for v in scan["violations"]))
        else:
            st.success("Blocklist scan clean.")
        if exec_state.get("execution"):
            ex = exec_state["execution"]
            st.markdown(f"**Executed at** {ex['executed_at']} · took {ex['duration_sec']}s (simulated)")
            st.code("\n".join(ex["log"]), language="text")
        st.markdown("**Rollback CLI (pre-staged):**")
        st.code("\n".join(bundle["rollback_cli"]), language="text")

    if exec_state.get("verification"):
        ver = exec_state["verification"]
        vstatus = "done" if ver["passed"] else "blocked"
        with st.expander(f"🔬 Verification — {STATUS_ICON.get(vstatus)} "
                         f"{'all checks passed' if ver['passed'] else 'FAILED'}", expanded=True):
            for c in ver["checks"]:
                st.markdown(f"{'✅' if c['passed'] else '❌'} **{c['name']}** — {c['detail']}")


def render_audit_trail():
    with st.expander("🗃️ Audit trail (SQLite)", expanded=False):
        rows = audit.fetch_all()
        if not rows:
            st.caption("No audit entries yet.")
            return
        df = pd.DataFrame(rows)[["id", "ts", "user_role", "decision", "blocked_stage",
                                  "risk_level", "risk_score", "reviewer_verdict",
                                  "approver", "request_text"]]
        st.dataframe(df, width="stretch", hide_index=True)
        pick = st.selectbox("Executive summary for change #",
                            [r["id"] for r in rows], key="audit_pick")
        row = next(r for r in rows if r["id"] == pick)
        st.markdown(f"> {row['executive_summary'] or '_no summary_'}")
        if row.get("generated_cli"):
            st.code(row["generated_cli"], language="text")


# ----------------------------------------------------------------------------- app
_init_state()

with st.sidebar:
    st.markdown("## 🛰️ NetPilot AI")
    st.caption("Explainable Agentic NetOps")
    role = st.radio("Your role", ["engineer", "approver"], horizontal=True,
                    help="Engineers can request changes; only approvers can approve execution.")
    simulate_window = st.toggle("Simulate maintenance window active", value=False,
                                help="Real window: Sunday 02:00–04:00. Toggle for demos.")
    st.divider()
    st.caption(f"Model: `{config.OPENAI_MODEL}`")
    st.caption(f"Embeddings: `{config.OPENAI_EMBED_MODEL}`")
    st.caption("All devices are mocked — nothing real is touched.")
    if st.button("🔄 New request", width="stretch"):
        _reset_run()
        st.rerun()

st.title("🛰️ NetPilot AI")
st.markdown("**Plan → Evidence → Policy → Risk → Review → Explain → Approve → Execute → Verify.** "
            "Every network change goes through the full board — the AI never just answers.")

if not config.api_key_present():
    st.error("`OPENAI_API_KEY` is not set. Copy `.env.example` to `.env`, add your key, and restart.")
    st.stop()

# --- request input -----------------------------------------------------------
cols = st.columns(len(EXAMPLES))
for col, (label, prompt) in zip(cols, EXAMPLES):
    if col.button(label, width="stretch"):
        st.session_state.queued_request = prompt

with st.form("request_form", clear_on_submit=False):
    text = st.text_input("Describe the network change...",
                         value=st.session_state.request_text,
                         placeholder="e.g. Migrate all premium customers on OLT-12 to VLAN 220 "
                                     "during tonight's maintenance window.")
    submitted = st.form_submit_button("Analyze change ▶", type="primary")
if submitted and text.strip():
    st.session_state.queued_request = text.strip()

# --- run analysis phase ------------------------------------------------------
if st.session_state.queued_request:
    req = st.session_state.queued_request
    st.session_state.queued_request = None
    st.session_state.request_text = req
    _reset_run()
    with st.status("🤖 Agentic pipeline running…", expanded=True) as status:
        def progress(stage, msg):
            status.write(msg)
        state = run_analysis(req, role=role, simulate_window=simulate_window, progress=progress)
        st.session_state.pipeline = state
        if state.get("error"):
            status.update(label="Pipeline error", state="error")
        elif state["blocked"]:
            status.update(label=f"⛔ Blocked at {state['blocked_stage']} stage", state="error")
        else:
            status.update(label="✅ Analysis complete — awaiting human decision", state="complete")
    st.rerun()

state = st.session_state.pipeline
if state:
    st.markdown(f"#### Request: “{state['request_text']}”")
    for w in state.get("warnings", []):
        st.warning(f"🛡️ Guardrail: {w}")

    if state.get("help"):
        render_help(state["help"])

    if state.get("error"):
        st.error(f"😵 The pipeline hit a problem and stopped safely.\n\n"
                 f"**{state['error']}**\n\nCheck your API key / network and try again.")
    if state["blocked"]:
        st.error(f"⛔ **CHANGE BLOCKED at the {state['blocked_stage'].upper()} stage** — "
                 f"{state['blocked_reason']}")

    stg = state["stages"]
    if stg["intent"].get("data"):
        render_intent(stg["intent"])
    if stg["plan"].get("data"):
        render_plan(stg["plan"])
    if stg["evidence"].get("evidence"):
        render_evidence(stg["evidence"], state.get("blocked_reason"))
    if stg["policy"].get("checks"):
        render_policy(stg["policy"])
    if stg["risk"].get("data"):
        render_risk(stg["risk"], stg.get("debate"))
    if stg["debate"].get("reviewer"):
        render_debate(stg["debate"], stg["plan"], stg["risk"])
    if stg["explanation"].get("data"):
        render_explanation(stg["explanation"])

    # ---- approval gate -------------------------------------------------------
    ready_for_decision = (state["analysis_complete"] and not state["blocked"]
                          and not state.get("error") and state.get("decision") is None
                          and st.session_state.approved_by is None)
    if ready_for_decision:
        st.divider()
        st.markdown("### 🧑‍⚖️ Human approval gate")
        final_level = stg["debate"].get("final_risk_level", "?")
        st.markdown(f"Final risk after review: {_risk_badge(final_level)}",
                    unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        allowed = policy.can_approve(role)
        with c1:
            if st.button("✅ Approve & execute", type="primary", disabled=not allowed,
                         width="stretch"):
                st.session_state.approved_by = role
                st.rerun()
            if not allowed:
                st.caption("🔒 Role 'engineer' cannot approve. Switch to **approver** in the sidebar.")
        with c2:
            if st.button("❌ Reject", width="stretch"):
                st.session_state.reject_mode = True
        if st.session_state.reject_mode:
            reason = st.text_input("Rejection reason (required, goes to the audit log)")
            if st.button("Confirm rejection") and reason.strip():
                log_rejection(state, approver=role, reason=reason.strip())
                st.session_state.reject_mode = False
                st.rerun()

    if state.get("decision") == "rejected":
        st.warning("❌ Change **rejected** by the human approver. Logged to the audit trail.")

    # ---- execution phase ------------------------------------------------------
    if st.session_state.approved_by and st.session_state.exec_state is None:
        st.divider()
        st.markdown("### ⚙️ Executing approved change (mock)")
        bar = st.progress(0.0)
        line = st.empty()

        def exec_progress(i, n, msg):
            bar.progress(i / n)
            line.markdown(f"`{msg}`")

        exec_state = run_execution(state, approver=st.session_state.approved_by,
                                   progress=exec_progress)
        st.session_state.exec_state = exec_state
        st.rerun()

    if st.session_state.exec_state:
        st.divider()
        if st.session_state.exec_state["status"] == "done":
            st.success("✅ Change executed and verified. Full record written to the audit log.")
        render_execution_cards(st.session_state.exec_state)
        if state.get("executive_summary"):
            st.markdown(f"**🧾 Executive summary (audit):** {state['executive_summary']}")

st.divider()
render_audit_trail()
