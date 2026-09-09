from app.core.risk import classify_risk


def test_high_risk():
    result = classify_risk(
        "approve refund"
    )

    assert result["level"] == "high"