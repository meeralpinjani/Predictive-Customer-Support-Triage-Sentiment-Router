"""The playbook's demo tickets (section 6.7) end to end through the API."""
from app.config import settings
from app.nlp import frustration_model


def post(client, customer_id, body, subject=""):
    res = client.post("/api/tickets", json={"customer_id": customer_id, "subject": subject, "body": body})
    assert res.status_code == 201
    return res.json()


def test_1_enterprise_outage_goes_senior_with_high_score(client):
    t = post(client, "c1", "Production DOWN for an hour. Cancelling if not fixed ASAP!!")
    assert t["route"] == "senior"
    assert "outage" in t["analysis"]["critical_flags"]
    assert t["priority"] >= settings.senior_score   # playbook illustrates "70+"; senior band either way
    assert "Critical rule" in t["route_reason"]


def test_2_free_password_reset_is_answered_automatically(client):
    t = post(client, "c15", "How do I reset my password?")
    assert t["priority"] < 15
    assert t["route"] == "auto_kb" and t["status"] == "kb_handled"
    assert "Did this help" in t["auto_reply"]


def test_3_pro_double_charge_goes_to_billing_specialist(client):
    t = post(client, "c14", "Charged twice this month, please refund today")
    assert t["route"] == "tier2"
    assert t["analysis"]["intent"] == "billing_dispute"
    assert t["assigned_agent"]["level"] == "tier2"
    assert 25 <= t["priority"] < 65


def test_4_invoice_question_is_answered_automatically(client):
    t = post(client, "c13", "Where can I download invoices? Thanks!")
    assert t["route"] == "auto_kb"
    assert t["kb"]["article_id"] == "kb_inv_02"


def test_5_angry_free_user_escalates_for_frustration(client):
    t = post(client, "c15", "This is the worst app, nobody replies!!!")
    assert t["route"] == "senior"
    assert t["analysis"]["frustration"] >= frustration_model.threshold("rules")
    assert t["route_reason"] == "High frustration"


def test_6_security_goes_senior_whatever_the_plan(client):
    t = post(client, "c14", "Someone logged into my account from another country")
    assert t["route"] == "senior"
    assert "security" in t["analysis"]["critical_flags"]


def test_7_feature_request_stays_low(client):
    t = post(client, "c13", "Would be nice to have dark mode")
    assert t["analysis"]["intent"] == "feature_request"
    assert t["priority"] < 40
    assert t["route"] in ("tier1", "auto_kb")   # dark mode exists, so the KB may answer it


def test_8_hinglish_payment_failure_goes_tier2(client):
    t = post(client, "c16", "Mera payment fail ho gaya, kal tak chahiye")
    assert t["analysis"]["language"] == "hi-en"
    assert t["analysis"]["intent"] == "billing_dispute"
    assert t["route"] == "tier2"


def test_high_value_account_at_renewal_risk_escalates(client):
    # Apex Cloud: enterprise, renewal in 10 days. A non-critical problem plus a negative tone.
    t = post(client, "c2", "Our reports are broken and the team is blocked today. Very disappointed.")
    assert "renewal_risk" in t["boosts"]
    assert t["route"] == "senior"
    assert t["route_reason"] in ("High-value customer", "High priority score", "High frustration")


def test_repeat_contact_adds_points(client):
    for _ in range(2):
        post(client, "c12", "The calendar sync shows the wrong times.")
    third = post(client, "c12", "The calendar sync shows the wrong times.")
    assert third["boosts"].get("repeat_contact") == 15
