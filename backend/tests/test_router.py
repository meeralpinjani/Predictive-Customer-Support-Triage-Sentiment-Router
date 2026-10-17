from app.config import settings
from app.services.router import decide, frustration_threshold

KB = (0.43, 0.66)


def test_critical_flag_routes_to_senior_regardless_of_score_or_value():
    d = decide(score=20, frustration=0.1, intent="security", flags=["security"], kb_conf=0.9, kb_thresholds=KB)
    assert d.route == "senior"
    assert "Critical rule" in d.reason
    assert d.kb_action == "none"


def test_legal_flag_notifies_manager():
    d = decide(score=20, frustration=0.1, intent="legal", flags=["legal"], kb_conf=0.0, kb_thresholds=KB)
    assert d.route == "senior" and "manager notified" in d.reason


def test_high_frustration_routes_to_senior():
    d = decide(score=30, frustration=max(0.8, frustration_threshold()), intent="bug", flags=[], kb_conf=0.0,
               kb_thresholds=KB)
    assert d.route == "senior"
    assert d.reason == "High frustration"


def test_high_value_customer_escalates():
    d = decide(score=55, frustration=0.1, intent="other", flags=[], kb_conf=0.0, value=0.85, kb_thresholds=KB)
    assert d.route == "senior" and d.reason == "High-value customer"
    # Same ticket from an average customer stays in Tier 2.
    d2 = decide(score=55, frustration=0.1, intent="other", flags=[], kb_conf=0.0, value=0.4, kb_thresholds=KB)
    assert d2.route == "tier2"


def test_auto_kb_resolution():
    d = decide(score=10, frustration=0.05, intent="password_reset", flags=[], kb_conf=0.85, kb_thresholds=KB)
    assert d.route == "auto_kb"
    assert d.kb_action == "auto_reply"


def test_low_confidence_never_auto_answers():
    d = decide(score=10, frustration=0.05, intent="password_reset", flags=[], kb_conf=0.85,
               confidence=settings.min_auto_confidence - 0.1, kb_thresholds=KB)
    assert d.route == "tier1" and d.kb_action == "suggest"


def test_score_thresholds():
    def route(score):
        return decide(score=score, frustration=0.1, intent="other", flags=[], kb_conf=0.1, kb_thresholds=KB)
    assert route(settings.senior_score).route == "senior"
    assert route(settings.senior_score - 1).route == "tier2"
    assert route(settings.tier2_score).route == "tier2"
    assert route(settings.tier2_score - 1).route == "tier1"


def test_specialist_issues_go_to_tier2_even_with_low_score():
    d = decide(score=20, frustration=0.1, intent="billing_dispute", flags=[], kb_conf=0.0, kb_thresholds=KB)
    assert d.route == "tier2" and d.reason == "Needs a billing specialist"


def test_kb_suggestion_gating_and_abstention():
    d_suggest = decide(score=20, frustration=0.1, intent="other", flags=[], kb_conf=0.50, kb_thresholds=KB)
    assert d_suggest.route == "tier1" and d_suggest.kb_action == "suggest"
    d_abstain = decide(score=20, frustration=0.1, intent="other", flags=[], kb_conf=0.40, kb_thresholds=KB)
    assert d_abstain.kb_action == "none"


def test_what_if_threshold_overrides():
    d = decide(score=50, frustration=0.1, intent="other", flags=[], kb_conf=0.0, kb_thresholds=KB, senior_score=45)
    assert d.route == "senior"
