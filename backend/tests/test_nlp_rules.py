from app.nlp import frustration_model
from app.nlp.analyzer import analyse
from app.nlp.rules import analyse_rules, critical_flags, detect_language

HIGH = frustration_model.threshold("rules")


def test_outage_ticket():
    res = analyse_rules("Our production dashboard has been DOWN for an hour. This is unacceptable, "
                        "we will cancel if this is not fixed ASAP!")
    assert res.intent == "outage"
    assert res.urgency >= 0.9
    assert res.frustration >= HIGH
    assert "outage" in res.critical_flags


def test_password_reset_ticket():
    res = analyse_rules("How do I reset my password?")
    assert res.intent == "password_reset"
    assert res.urgency <= 0.2
    assert res.frustration < 0.2
    assert res.critical_flags == []


def test_billing_dispute_ticket():
    res = analyse_rules("I was charged twice this month. Please refund today.")
    assert res.intent == "billing_dispute"
    assert 0.55 <= res.urgency <= 0.75
    assert res.frustration < HIGH
    assert res.critical_flags == []


def test_angry_bug_ticket_is_highly_frustrated():
    res = analyse_rules("This is the worst app, nothing works and nobody replies!!!")
    assert res.intent == "bug"
    assert 0.40 <= res.urgency <= 0.60
    assert res.frustration >= HIGH
    assert res.critical_flags == []


def test_politeness_does_not_cancel_anger():
    angry = analyse_rules("This is ridiculous, I'm furious and fed up!")
    polite_angry = analyse_rules("Please, thank you. This is ridiculous, I'm furious and fed up!")
    assert polite_angry.frustration >= HIGH
    assert abs(polite_angry.frustration - angry.frustration) < 0.05


def test_sarcasm_is_caught():
    res = analyse_rules("Great, just great. Thanks for nothing.")
    assert res.signals["anger"] > 0.5
    assert res.frustration >= HIGH


def test_security_breach_ticket():
    res = analyse_rules("Someone logged in to my account from another country")
    assert res.intent == "security"
    assert res.urgency == 1.0
    assert "security" in res.critical_flags


def test_feature_request_ticket():
    res = analyse_rules("Would be nice to have dark mode")
    assert res.intent == "feature_request"
    assert res.urgency <= 0.1
    assert res.frustration < 0.2


def test_legal_threat_ticket():
    res = analyse_rules("Our lawyer has instructed us to take legal action and file a lawsuit in court immediately")
    assert res.intent == "legal"
    assert res.urgency >= 0.9
    assert res.manager_flag is True


def test_safety_hazard_ticket():
    res = analyse_rules("The backup battery is smoking and overheating, which is an unsafe hazard")
    assert res.intent == "safety"
    assert res.urgency == 1.0


def test_negation_and_false_friends_do_not_trigger_critical_flags():
    assert critical_flags("We were not hacked, I just want to enable 2FA.") == []
    assert critical_flags("Nothing was stolen, but how do I change my password?") == []
    assert critical_flags("Our smoke tests fail on the staging build.") == []
    assert critical_flags("Please confirm the SLA breach credit on our invoice.") == []
    assert critical_flags("Someone hacked my account!") == ["security"]


def test_hinglish_is_detected_and_understood():
    res = analyse_rules("Mera payment fail ho gaya par paisa kat gaya, refund chahiye. Kal tak chahiye.")
    assert res.language == "hi-en"
    assert res.intent == "billing_dispute"
    assert res.urgency >= 0.65
    assert detect_language("How do I reset my password?") == "en"


def test_shouting_ignores_acronyms():
    calm = analyse_rules("How do I configure SAML SSO with our IdP and the API?")
    assert calm.signals["style"] == 0.0


def test_analyzer_wrapper_rules_mode():
    text = "How do I reset my password?"
    direct, wrapped = analyse_rules(text), analyse(text)
    assert wrapped.mode == "rules"
    assert (wrapped.intent, wrapped.urgency, wrapped.frustration) == (direct.intent, direct.urgency, direct.frustration)
