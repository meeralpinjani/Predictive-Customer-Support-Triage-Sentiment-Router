"""Guards the reported numbers: the rules engine on the held-out test split, and the simulation."""
from eval import evaluate_kb, evaluate_nlp
from eval.simulate import run_simulation


def test_rules_engine_meets_targets_on_held_out_tickets():
    res = evaluate_nlp.evaluate("rules")
    assert res["n"] >= 100
    assert res["urgency"]["macro_f1"] >= 0.75
    assert res["critical"]["recall"] >= 0.9
    assert res["frustration"]["precision"] >= 0.85
    assert res["frustration"]["recall"] >= 0.75
    assert res["escalation"]["precision"] >= 0.80
    assert res["auto_answer"]["safe_precision"] >= 0.85
    assert res["latency_ms"]["mean"] < 2000


def test_kb_auto_answers_are_accurate():
    res = evaluate_kb.evaluate("rules")
    assert res["test"]["auto_accuracy"] >= 0.90
    assert res["test"]["out_of_scope_auto"] == 0


def test_router_beats_fcfs_without_starving_anyone():
    sim = run_simulation("rules")
    fcfs, router = sim["policies"]["fcfs"], sim["policies"]["router"]
    assert router["urgent_avg"] < 0.7 * fcfs["urgent_avg"]
    assert router["high_value_avg"] < 0.5 * fcfs["high_value_avg"]
    assert router["sla_breaches"] < fcfs["sla_breaches"]
