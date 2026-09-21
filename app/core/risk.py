HIGH_RISK_TERMS = [
    "approve",
    "approval",
    "refund",
    "payment exception",
    "terminate",
    "waive",
    "override",
    "execute payment",
    "close account",
]


def classify_risk(text):
    value = text.lower()

    matches = [
        term
        for term in HIGH_RISK_TERMS
        if term in value
    ]

    return {
        "level": "high" if matches else "low",
        "matched_terms": matches,
    }