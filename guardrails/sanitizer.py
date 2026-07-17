"""Input sanitizer — first line of defense against prompt injection."""
import re

MAX_INPUT_CHARS = 1500

# Patterns that look like attempts to reprogram the agents.
_INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts)",
    r"disregard (your|the) (system|previous) (prompt|instructions)",
    r"you are now\b",
    r"act as (an? )?(admin|root|developer mode)",
    r"system prompt",
    r"</?(system|assistant|tool)>",
    r"\bBEGIN (SYSTEM|ADMIN)\b",
]


def sanitize(text: str) -> dict:
    """Clean user input. Returns {"text": cleaned, "warnings": [...]}."""
    warnings = []
    cleaned = (text or "").strip()

    if len(cleaned) > MAX_INPUT_CHARS:
        cleaned = cleaned[:MAX_INPUT_CHARS]
        warnings.append(f"Input truncated to {MAX_INPUT_CHARS} characters.")

    # Strip control characters
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)

    for pat in _INJECTION_PATTERNS:
        if re.search(pat, cleaned, flags=re.IGNORECASE):
            warnings.append(
                "Possible prompt-injection phrasing detected and flagged; the request is "
                "processed as plain data only."
            )
            break

    return {"text": cleaned, "warnings": warnings}
