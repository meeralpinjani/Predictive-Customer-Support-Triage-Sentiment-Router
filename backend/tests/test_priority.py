from app.config import SLA_RISK_POINTS
from app.services.priority import compute_priority as cp


def test_worked_examples():
    # (urgency, frustration, value, wait, sla) with the tuned weights 0.25 F / 0.25 U / 0.30 V / 0.20 age
    a = cp(0.90, 0.85, 0.90, 0, 240)
    assert a.score == 71
    assert a.contributions == {"urgency": 22.5, "frustration": 21.2, "value": 27.0, "age": 0.0}
    assert cp(0.10, 0.05, 0.10, 0, 240).score == 7          # B: password reset
    assert cp(0.60, 0.40, 0.50, 0, 240).score == 40         # C: double charge
    assert cp(0.60, 0.40, 0.50, 120, 240).score == 50       # C after 2 hours


def test_reasons_name_the_two_strongest_signals():
    res = cp(0.90, 0.85, 0.90, 0, 240)
    assert res.reasons == ["High-value customer (90%)", "Time-critical issue (90%)"]


def test_rule_boosts_add_points_and_explain_themselves():
    res = cp(0.30, 0.10, 0.30, 0, 240, boosts={"repeat_contact": 15})
    assert res.score == cp(0.30, 0.10, 0.30, 0, 240).score + 15
    assert any(r.startswith("Contacted 3+ times") for r in res.reasons)


def test_sla_risk_ramp_prevents_starvation_but_not_routing():
    sla = 240
    before = cp(0.10, 0.05, 0.10, 0.74 * sla, sla)
    assert "sla_risk" not in before.boosts
    mid = cp(0.10, 0.05, 0.10, 1.0 * sla, sla)
    assert 0 < mid.boosts["sla_risk"] < SLA_RISK_POINTS
    full = cp(0.10, 0.05, 0.10, 1.5 * sla, sla)
    assert full.boosts["sla_risk"] == SLA_RISK_POINTS
    # A starving low-priority ticket now outranks a fresh, fairly important one...
    assert full.score > cp(0.60, 0.40, 0.50, 0, 240).score
    # ...but the SLA ramp never pushes it up a support tier.
    assert full.route_score == full.score - SLA_RISK_POINTS


def test_score_is_capped_at_100():
    assert cp(1.0, 1.0, 1.0, 10_000, 60, boosts={"repeat_contact": 15}).score == 100
