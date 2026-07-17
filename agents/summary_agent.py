"""Executive Summary Agent: one audit-ready paragraph per change."""
from agents.base import call_json_agent
from agents.schemas import ExecutiveSummary

SYSTEM_PROMPT = """You are the Executive Summary Agent of NetPilot AI. Write ONE paragraph
(max 90 words) for the audit log describing this change: what was requested, what the platform
decided and why, the final risk level, and the outcome (executed/blocked/rejected + verification
result if executed). Plain business language, past tense, no jargon beyond device/VLAN names.

Respond with JSON: {"summary": "<the paragraph>"}"""


def summarize(context: dict) -> str:
    try:
        result = call_json_agent("ExecutiveSummaryAgent", SYSTEM_PROMPT, context,
                                 ExecutiveSummary, temperature=0.2, max_tokens=200)
        return result.summary
    except Exception:
        # The audit log must never fail because of the summarizer.
        return (f"Change request '{context.get('request_text', '?')}' ended with outcome "
                f"'{context.get('outcome', '?')}'. (Automatic summary unavailable.)")
