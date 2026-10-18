from app.config import settings
from app.services.router import decide, frustration_threshold

KB = (0.43, 0.66)


def test_critical_flag_goes_to_level3_regardless_of_score_or_category():
    d = decide(score=20, frustration=0.1, intent="security", flags=["security"], kb_conf=0.9, kb_thresholds=KB,
               category="feedback")
    assert d.route == "level3" and "Emergency" in d.reason and d.kb_action == "none"


def test_legal_flag_notifies_manager():
    d = decide(score=20, frustration=0.1, intent="legal", flags=["legal"], kb_conf=0.0, kb_thresholds=KB)
    assert d.route == "level3" and "manager notified" in d.reason


def test_high_frustration_escalates():
    d = decide(score=30, frustration=max(0.8, frustration_threshold()), intent="bug", flags=[], kb_conf=0.0,
               kb_thresholds=KB)
    assert d.route == "level3" and d.reason == "High frustration"


def test_high_value_customer_escalates():
    d = decide(score=55, frustration=0.1, intent="other", flags=[], kb_conf=0.0, value=0.85, kb_thresholds=KB)
    assert d.route == "level3" and d.reason == "High-value customer"
    d2 = decide(score=55, frustration=0.1, intent="other", flags=[], kb_conf=0.0, value=0.4, kb_thresholds=KB)
    assert d2.route == "level1"


def test_auto_kb_resolution_and_low_confidence():
    d = decide(score=10, frustration=0.05, intent="password_reset", flags=[], kb_conf=0.85, kb_thresholds=KB)
    assert d.route == "auto_kb" and d.kb_action == "auto_reply"
    low = decide(score=10, frustration=0.05, intent="password_reset", flags=[], kb_conf=0.85,
                 confidence=settings.min_auto_confidence - 0.1, kb_thresholds=KB)
    assert low.route == "level1" and low.kb_action == "suggest"


def test_score_escalation_threshold():
    def route(score):
        return decide(score=score, frustration=0.1, intent="other", flags=[], kb_conf=0.1, kb_thresholds=KB).route
    assert route(settings.level3_score) == "level3"
    assert route(settings.level3_score - 1) == "level1"


def test_category_sets_floor_and_technical_intent_lifts():
    assert decide(score=20, frustration=0.1, intent="other", flags=[], kb_conf=0.0, kb_thresholds=KB,
                  category="data").route == "level2"
    assert decide(score=20, frustration=0.1, intent="bug", flags=[], kb_conf=0.0, kb_thresholds=KB,
                  category="howto").route == "level2"
    assert decide(score=20, frustration=0.1, intent="billing_dispute", flags=[], kb_conf=0.0, kb_thresholds=KB,
                  category="billing").route == "level1"


def test_kb_suggestion_gating():
    assert decide(score=20, frustration=0.1, intent="other", flags=[], kb_conf=0.50, kb_thresholds=KB).kb_action == "suggest"
    assert decide(score=20, frustration=0.1, intent="other", flags=[], kb_conf=0.40, kb_thresholds=KB).kb_action == "none"


def test_what_if_threshold_override():
    d = decide(score=50, frustration=0.1, intent="other", flags=[], kb_conf=0.0, kb_thresholds=KB, level3_score=45)
    assert d.route == "level3"
