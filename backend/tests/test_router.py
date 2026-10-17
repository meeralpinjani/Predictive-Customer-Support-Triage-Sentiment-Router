from app.config import settings
from app.services.router import decide


def test_critical_flag_routes_to_senior_regardless_of_score_or_value():
    # Low score (20), no frustration, free user, but critical flag present
    d = decide(score=20, frustration=0.1, intent="security", flags=["security"], kb_conf=0.9)
    assert d.route == "senior"
    assert "Critical rule" in d.reason
    assert d.kb_action == "none"


def test_high_frustration_routes_to_senior():
    # Score 30 (< 35), but frustration 0.80 >= 0.75
    d = decide(score=30, frustration=0.80, intent="bug", flags=[], kb_conf=0.0)
    assert d.route == "senior"
    assert d.reason == "High frustration"
    assert d.kb_action == "none"


def test_auto_kb_resolution():
    # Routine intent, low frustration (< 0.4), low score (< 35), high KB confidence (>= 0.75)
    d = decide(score=10, frustration=0.05, intent="password_reset", flags=[], kb_conf=0.85)
    assert d.route == "auto_kb"
    assert d.kb_action == "auto_reply"


def test_score_thresholds():
    # Score 60 -> Senior
    d60 = decide(score=60, frustration=0.2, intent="bug", flags=[], kb_conf=0.1)
    assert d60.route == "senior"
    assert d60.reason == "High priority score"

    # Score 59 -> Tier 2
    d59 = decide(score=59, frustration=0.2, intent="bug", flags=[], kb_conf=0.1)
    assert d59.route == "tier2"
    assert d59.reason == "Moderate priority score"

    # Score 35 -> Tier 2
    d35 = decide(score=35, frustration=0.2, intent="bug", flags=[], kb_conf=0.1)
    assert d35.route == "tier2"
    assert d35.reason == "Moderate priority score"

    # Score 34 -> Tier 1
    d34 = decide(score=34, frustration=0.2, intent="bug", flags=[], kb_conf=0.1)
    assert d34.route == "tier1"
    assert d34.reason == "Routine request"


def test_kb_suggestion_gating_and_abstention():
    # KB confidence >= 0.55 triggers suggestion for Tier 1
    d_suggest = decide(score=20, frustration=0.1, intent="how_to", flags=[], kb_conf=0.60)
    assert d_suggest.route == "tier1"
    assert d_suggest.kb_action == "suggest"

    # KB confidence < 0.55 abstains
    d_abstain = decide(score=20, frustration=0.1, intent="how_to", flags=[], kb_conf=0.45)
    assert d_abstain.route == "tier1"
    assert d_abstain.kb_action == "none"
