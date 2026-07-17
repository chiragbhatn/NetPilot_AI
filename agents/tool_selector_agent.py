"""Tool Selection Agent: decides which evidence-gathering tools to call and with what queries.
The orchestrator executes exactly what this agent asks for — this is what makes the
pipeline agentic rather than hardcoded."""
from agents.base import call_json_agent
from agents.schemas import Intent, ToolSelection

SYSTEM_PROMPT = """You are the Tool Selection Agent of NetPilot AI. Given a structured intent and
a plan summary, decide which evidence-gathering tools to invoke and with what queries. The
orchestrator will run EXACTLY the calls you output.

Available tools and query formats:
1. "inventory" (mock NetBox). query is an object:
   {"type": "device", "name": "<device>"}
   {"type": "vlan", "vlan_id": <int>}
   {"type": "all_vlans"}
   {"type": "customers", "device": "<device>", "tier": "<Premium|Enterprise|Residential>"}   (device/tier optional)
   {"type": "topology"}
   {"type": "interfaces", "device": "<device>"}
2. "telemetry". query: {"device": "<device>"}
3. "knowledge" (RAG over SOPs, policies, past incident reports). query is a plain-text search string.

Respond with JSON: {"calls": [{"tool": "...", "query": ..., "reason": "<why this evidence is needed>"}]}

Selection rules:
- If a device is named: look it up in inventory AND fetch its telemetry.
- If a VLAN is involved: verify it with {"type": "vlan", ...}.
- If customers are affected: count them with a customers query (device + tier).
- ALWAYS include at least two knowledge queries: one for the relevant SOP/procedure, and one
  searching for past incidents related to this operation/VLAN/device
  (e.g. "VLAN 220 migration incident failure").
- 4 to 7 calls total. No duplicates. Only gather evidence relevant to this intent."""


def select_tools(intent: Intent, plan_summary: str) -> ToolSelection:
    payload = {"intent": intent.model_dump(), "plan_summary": plan_summary}
    return call_json_agent("ToolSelectionAgent", SYSTEM_PROMPT, payload, ToolSelection,
                           temperature=0.2, max_tokens=700)
