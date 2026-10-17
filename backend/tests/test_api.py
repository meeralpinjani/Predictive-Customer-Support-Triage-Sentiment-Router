from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_post_then_get_flow():
    payload = {
        "customer_id": "c3",
        "subject": "Double invoice dispute",
        "body": "I was charged twice this month. Please refund today.",
        "channel": "web",
    }
    create_res = client.post("/api/tickets", json=payload)
    assert create_res.status_code == 201
    created = create_res.json()
    t_id = created["id"]

    get_res = client.get(f"/api/tickets/{t_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == t_id


def test_404_on_missing_ticket():
    res = client.get("/api/tickets/9999999")
    assert res.status_code == 404


def test_422_on_invalid_input():
    # Empty body is invalid
    res = client.post("/api/tickets", json={"customer_id": "c1", "subject": "Test", "body": ""})
    assert res.status_code == 422


def test_override_requires_reason_and_locks_route():
    # Create ticket
    payload = {
        "customer_id": "c9",
        "subject": "Simple query",
        "body": "How do I change my nickname?",
        "channel": "web",
    }
    t = client.post("/api/tickets", json=payload).json()
    t_id = t["id"]

    # Fails if reason is too short (< 3 chars)
    invalid_override = client.post(f"/api/tickets/{t_id}/override", json={"route": "senior", "reason": "no"})
    assert invalid_override.status_code == 422

    # Succeeds with valid reason
    valid_override = client.post(
        f"/api/tickets/{t_id}/override",
        json={"route": "senior", "priority": 85, "reason": "Escalating per executive request"},
    )
    assert valid_override.status_code == 200
    res = valid_override.json()
    assert res["route"] == "senior"
    assert res["priority"] == 85
    assert res["route_locked"] is True
    assert "Agent override" in res["route_reason"]


def test_resolve_endpoint():
    t = client.post("/api/tickets", json={"body": "Need quick help"}).json()
    t_id = t["id"]

    resolve_res = client.post(f"/api/tickets/{t_id}/resolve")
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "resolved"


def test_kb_not_helpful_feedback_escalation():
    # Submit auto-reply eligible ticket
    payload = {
        "customer_id": "c9",
        "subject": "Resetting Your Account Password",
        "body": "How do I reset my password? Forgot my password what should I do?",
        "channel": "web",
    }
    t = client.post("/api/tickets", json=payload).json()
    t_id = t["id"]
    assert t["status"] == "kb_handled"

    # Submit kb_not_helpful feedback
    fb_res = client.post(
        f"/api/tickets/{t_id}/feedback",
        json={"kind": "kb_not_helpful", "note": "Link was expired"},
    )
    assert fb_res.status_code == 200
    updated = fb_res.json()
    assert updated["status"] == "queued"
    assert updated["route"] == "tier1"
    assert updated["kb"]["action"] == "none"


def test_customers_and_stats_endpoints():
    cust_res = client.get("/api/customers")
    assert cust_res.status_code == 200
    customers = cust_res.json()
    assert len(customers) >= 8

    stats_res = client.get("/api/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_tickets"] > 0
    assert "tier1" in stats["counts_by_route"] or "senior" in stats["counts_by_route"]
    assert stats["override_rate"] >= 0.0

    admin_res = client.post("/api/admin/rescore")
    assert admin_res.status_code == 200
    assert admin_res.json()["status"] == "ok"
