from app.services.priority import compute_priority as cp


def test_examples():
    # Ticket A: Enterprise Outage
    res_a = cp(0.90, 0.85, 1.0, 0, 240)
    assert res_a.score == 68
    assert res_a.components["urgency"] == 0.90
    assert res_a.contributions["urgency"] == 31.5
    assert len(res_a.reasons) > 0

    # Ticket B: Free Password Reset
    assert cp(0.10, 0.05, 0.1, 0, 240).score == 6

    # Ticket C: Pro Billing Dispute
    assert cp(0.60, 0.40, 0.6, 0, 240).score == 40

    # Ticket C after 96 min waiting
    assert cp(0.60, 0.40, 0.6, 96, 240).score == 50

    # Ticket D: Free Angry Bug Report
    assert cp(0.45, 0.80, 0.1, 0, 240).score == 37

    # Ticket E: Free Security Breach Alert
    assert cp(1.00, 0.30, 0.1, 0, 240).score == 44
