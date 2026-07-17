"""Intent Agent: natural language -> strict structured intent JSON."""
from agents.base import call_json_agent
from agents.schemas import Intent

SYSTEM_PROMPT = """You are the Intent Agent of NetPilot AI, a network change-management platform
for an ISP (Huawei GPON OLTs behind a Cisco aggregation/core).

Convert the user's request into a single JSON object with EXACTLY these fields:
{
  "intent": "<one-sentence restatement>",
  "operation": "<vlan_migration | vlan_change | delete_vlan | reboot | interface_change | config_change | diagnostic | help | other>",
  "target_customers": "<who is affected, e.g. 'premium customers on OLT-12', or null>",
  "device": "<primary device name like OLT-12, SW-01, RTR-01, or null>",
  "vlan": <target VLAN id as integer, or null>,
  "urgency": "<low | normal | high | emergency>",
  "maintenance_window_required": <true unless the request is purely read-only/diagnostic>
}

Rules:
- Moving customers/services from one VLAN to another = "vlan_migration"; "vlan" is the TARGET VLAN.
- Removing/deleting a VLAN = "delete_vlan"; "vlan" is the VLAN being deleted.
- "urgency" is "emergency" only if the user explicitly declares an outage/emergency.
- Do not invent devices or VLANs that the user did not mention.
- Questions about network state/health/telemetry (e.g. "why is utilization high?") = "diagnostic".
- Questions about NetPilot itself — what it can do, its capabilities, how it works, which VLANs/
  devices/customers exist, what roles or policies there are, "help", "what can I ask" =
  operation "help".
- Greetings, small talk, jokes, poems, coding help, general knowledge, or ANY request that is not
  an operation on this network = operation "other" (the platform will refuse it). When in doubt
  between "other" and anything else, use "other"; between "help" and "diagnostic", use "help"
  for listings/capabilities and "diagnostic" for live health questions."""


def parse_intent(user_text: str) -> Intent:
    return call_json_agent("IntentAgent", SYSTEM_PROMPT, user_text, Intent,
                           temperature=0.2, max_tokens=300)
