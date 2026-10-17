from eval.evaluate_nlp import evaluate_nlp
from eval.simulate import run_simulation


def test_evaluate_nlp_metrics():
    res = evaluate_nlp()
    assert res["total_evaluated"] >= 200
    u = res["urgency"]
    # Urgent recall must meet or exceed target 0.85
    assert u["recall"] >= 0.85
    assert u["precision"] >= 0.80
    assert u["f1"] >= 0.80


def test_simulate_priority_improves_urgent_wait():
    res = run_simulation()
    fcfs_urgent_wait = res["fcfs"]["urgent_avg"]
    prio_urgent_wait = res["priority"]["urgent_avg"]

    # Priority queue must significantly reduce urgent waiting time compared to FCFS
    assert prio_urgent_wait < fcfs_urgent_wait
    reduction_pct = ((fcfs_urgent_wait - prio_urgent_wait) / fcfs_urgent_wait) * 100
    assert reduction_pct > 50.0  # At least 50% improvement
