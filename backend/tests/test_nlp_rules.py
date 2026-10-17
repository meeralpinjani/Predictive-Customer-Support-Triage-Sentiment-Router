from app.nlp.analyzer import analyse
from app.nlp.rules import analyse_rules


def test_outage_ticket():
    text = "Our production dashboard has been DOWN for an hour. This is unacceptable, we will cancel if this is not fixed ASAP!"
    res = analyse_rules(text)
    assert res.intent == "outage"
    assert res.urgency >= 0.9
    assert res.frustration >= 0.5
    assert "outage" in res.critical_flags


def test_password_reset_ticket():
    text = "How do I reset my password?"
    res = analyse_rules(text)
    assert res.intent == "password_reset"
    assert res.urgency <= 0.2
    assert res.frustration <= 0.1
    assert len(res.critical_flags) == 0


def test_billing_dispute_ticket():
    text = "I was charged twice this month. Please refund today."
    res = analyse_rules(text)
    assert res.intent == "billing_dispute"
    assert 0.55 <= res.urgency <= 0.75
    assert res.frustration <= 0.3
    assert len(res.critical_flags) == 0


def test_frustration_bug_ticket():
    text = "This is the worst app, nothing works and nobody replies!!!"
    res = analyse_rules(text)
    assert res.intent == "bug"
    assert 0.40 <= res.urgency <= 0.60
    assert res.frustration >= 0.75
    assert len(res.critical_flags) == 0


def test_security_breach_ticket():
    text = "Someone logged in to my account from another country"
    res = analyse_rules(text)
    assert res.intent == "security"
    assert res.urgency == 1.0
    assert res.frustration <= 0.3
    assert "security" in res.critical_flags


def test_feature_request_ticket():
    text = "Would be nice to have dark mode"
    res = analyse_rules(text)
    assert res.intent == "feature_request"
    assert res.urgency <= 0.1
    assert res.frustration <= 0.1
    assert len(res.critical_flags) == 0


def test_legal_threat_ticket():
    text = "Our lawyer has instructed us to take legal action and file a lawsuit in court immediately"
    res = analyse_rules(text)
    assert res.intent == "legal"
    assert res.urgency >= 0.9
    assert "legal" in res.critical_flags


def test_safety_hazard_ticket():
    text = "The backup battery is smoking and overheating, which is an unsafe hazard"
    res = analyse_rules(text)
    assert res.intent == "safety"
    assert res.urgency == 1.0
    assert "safety" in res.critical_flags


def test_analyzer_wrapper_rules_mode():
    text = "How do I reset my password?"
    res_direct = analyse_rules(text)
    res_wrapped = analyse(text)
    assert res_wrapped.mode == "rules"
    assert res_wrapped.intent == res_direct.intent
    assert res_wrapped.urgency == res_direct.urgency
    assert res_wrapped.frustration == res_direct.frustration
