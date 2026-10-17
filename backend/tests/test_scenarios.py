from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_scenario_1_outage():
    # 1. Enterprise: "Our production dashboard is DOWN. We will cancel if this is not fixed ASAP!"
    # Expected: Critical outage rule, Senior
    res = client.post("/api/tickets", json={
        "customer_id": "c1",
        "subject": "Emergency outage",
        "body": "Our production dashboard is DOWN. We will cancel if this is not fixed ASAP!",
    }).json()
    assert res["route"] == "senior"
    assert "outage" in res["analysis"]["critical_flags"]
    assert "Critical rule" in res["route_reason"]


def test_scenario_2_password():
    # 2. Free: "How do I reset my password?"
    # Expected: KB suggestion or auto-reply, low score
    res = client.post("/api/tickets", json={
        "customer_id": "c9",
        "subject": "Password reset",
        "body": "How do I reset my password?",
    }).json()
    assert res["priority"] < 35
    assert res["route"] in ("auto_kb", "tier1")
    assert res["kb"]["confidence"] >= 0.55
    assert res["kb"]["action"] in ("suggest", "auto_reply")


def test_scenario_3_duplicate_charge():
    # 3. Pro: "I was charged twice this month. Please refund today."
    # Expected: Tier 2 (billing)
    res = client.post("/api/tickets", json={
        "customer_id": "c3",
        "subject": "Billing issue",
        "body": "I was charged twice this month. Please refund today.",
    }).json()
    assert res["route"] == "tier2"
    assert res["analysis"]["intent"] == "billing_dispute"
    assert 35 <= res["priority"] < 60


def test_scenario_4_high_frustration():
    # 4. Free: "This is the worst app, nothing works and nobody replies!!!"
    # Expected: High frustration, Senior
    res = client.post("/api/tickets", json={
        "customer_id": "c10",
        "subject": "Unhappy user",
        "body": "This is the worst app, nothing works and nobody replies!!!",
    }).json()
    assert res["route"] == "senior"
    assert res["analysis"]["frustration"] >= 0.75
    assert "High frustration" in res["route_reason"]


def test_scenario_5_security_breach():
    # 5. Free: "Someone logged in from another country"
    # Expected: Security rule, Senior (Value did not matter)
    res = client.post("/api/tickets", json={
        "customer_id": "c9",
        "subject": "Suspicious activity",
        "body": "Someone logged in from another country",
    }).json()
    assert res["route"] == "senior"
    assert "security" in res["analysis"]["critical_flags"]
    assert "Critical rule" in res["route_reason"]


def test_scenario_6_dark_mode():
    # 6. Free: "Would be nice to have dark mode"
    # Expected: Tier 1, low score
    res = client.post("/api/tickets", json={
        "customer_id": "c11",
        "subject": "Suggestion",
        "body": "Would be nice to have dark mode",
    }).json()
    assert res["route"] == "tier1"
    assert res["priority"] < 35
    assert res["analysis"]["intent"] == "feature_request"
