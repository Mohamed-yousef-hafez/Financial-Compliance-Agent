import re

PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?previous\s+instructions",
    r"reveal\s+(the\s+)?system\s+prompt",
    r"show\s+(the\s+)?system\s+prompt",
    r"developer\s+message",
]


def is_prompt_injection(text):
    value = text.lower()
    return any(re.search(pattern, value) for pattern in PATTERNS)


def require_tenant(tenant_id):
    if not tenant_id or not tenant_id.strip():
        raise ValueError("tenant_id is required")

    return tenant_id.strip()