import re

HIGH_RISK_ACTIONS = {
    "approve": [
        "payment", "transaction", "refund", "transfer", "payout"
    ],
    "authorize": [
        "payment", "transaction", "transfer", "payout"
    ],
    "execute": [
        "payment", "transaction", "transfer"
    ],
    "process": [
        "payment", "transaction", "refund", "transfer"
    ],
    "issue": ["refund"],
    "release": ["payment", "funds", "transfer"],
    "terminate": ["account", "contract"],
    "close": ["account"],
    "waive": ["fee", "requirement", "control"],
    "override": ["policy", "control", "limit", "approval"],
    "bypass": ["policy", "control", "approval"],
}


def classify_risk(text):
    value = (text or "").lower()
    matches = []

    for action, targets in HIGH_RISK_ACTIONS.items():
        if not re.search(r"\b" + re.escape(action) + r"\b", value):
            continue

        for target in targets:
            if re.search(r"\b" + re.escape(target) + r"\b", value):
                matches.append(f"{action} {target}")

    return {
        "level": "high" if matches else "low",
        "matched_terms": matches,
    }