PASSWORD = {
    "customer_id": "c9",
    "subject": "Resetting Your Account Password",
    "body": "How do I reset my password? Forgot my password what should I do?",
}


def test_post_then_get_flow(client):
    created = client.post("/api/tickets", json={
        "customer_id": "c3", "subject": "Double invoice dispute",
        "body": "I was charged twice this month. Please refund today.",
    })
    assert created.status_code == 201
    t = created.json()
    assert t["assigned_agent"]["level"] == t["route"]
    got = client.get(f"/api/tickets/{t['id']}")
    assert got.status_code == 200 and got.json()["id"] == t["id"]


def test_404_on_missing_ticket(client):
    assert client.get("/api/tickets/9999999").status_code == 404


def test_unknown_customer_is_rejected(client):
    res = client.post("/api/tickets", json={"customer_id": "nope", "body": "Hello"})
    assert res.status_code == 404


def test_422_on_invalid_input(client):
    assert client.post("/api/tickets", json={"customer_id": "c1", "body": ""}).status_code == 422
    assert client.post("/api/tickets", json={"body": "x", "channel": "fax"}).status_code == 422


def test_override_requires_reason_and_locks_route_and_priority(client):
    t = client.post("/api/tickets", json={"customer_id": "c9", "body": "How do I change my nickname?"}).json()
    bad = client.post(f"/api/tickets/{t['id']}/override", json={"route": "senior", "reason": "no"})
    assert bad.status_code == 422
    empty = client.post(f"/api/tickets/{t['id']}/override", json={"reason": "nothing to change"})
    assert empty.status_code == 422

    res = client.post(f"/api/tickets/{t['id']}/override",
                      json={"route": "senior", "priority": 85, "reason": "Escalating per executive request"}).json()
    assert res["route"] == "senior" and res["priority"] == 85
    assert res["route_locked"] is True and res["priority_locked"] is True
    assert "Agent override" in res["route_reason"]
    assert res["assigned_agent"]["level"] == "senior"


def test_agent_can_lower_priority_and_rescore_keeps_it(client):
    t = client.post("/api/tickets", json={"customer_id": "c1", "body": "Our production website is down!"}).json()
    client.post(f"/api/tickets/{t['id']}/override", json={"priority": 5, "reason": "Known incident, tracked elsewhere"})
    client.post("/api/admin/rescore")
    assert client.get(f"/api/tickets/{t['id']}").json()["priority"] == 5


def test_resolve_is_one_way(client):
    t = client.post("/api/tickets", json={"body": "Need quick help"}).json()
    first = client.post(f"/api/tickets/{t['id']}/resolve")
    assert first.status_code == 200 and first.json()["status"] == "resolved"
    assert client.post(f"/api/tickets/{t['id']}/resolve").status_code == 409
    assert client.post(f"/api/tickets/{t['id']}/override",
                       json={"route": "tier2", "reason": "too late"}).status_code == 409


def test_kb_not_helpful_escalates_and_rescored(client):
    t = client.post("/api/tickets", json=PASSWORD).json()
    assert t["status"] == "kb_handled"
    updated = client.post(f"/api/tickets/{t['id']}/feedback",
                          json={"kind": "kb_not_helpful", "note": "Link was expired"}).json()
    assert updated["status"] == "queued"
    assert updated["route"] == "tier1"
    assert updated["kb"]["action"] == "none"
    assert updated["analysis"]["frustration"] > t["analysis"]["frustration"]
    assert updated["assigned_agent"] is not None
    assert "did not help" in updated["route_reason"]


def test_kb_helpful_closes_ticket_and_can_only_be_rated_once(client):
    t = client.post("/api/tickets", json=PASSWORD).json()
    ok = client.post(f"/api/tickets/{t['id']}/feedback", json={"kind": "kb_helpful"})
    assert ok.status_code == 200 and ok.json()["status"] == "resolved"
    again = client.post(f"/api/tickets/{t['id']}/feedback", json={"kind": "kb_not_helpful"})
    assert again.status_code == 409


def test_rating_requires_a_kb_answer(client):
    t = client.post("/api/tickets", json={"customer_id": "c1", "body": "Our production server is down"}).json()
    assert client.post(f"/api/tickets/{t['id']}/feedback", json={"kind": "kb_helpful"}).status_code == 409


def test_customers_stats_and_rescore_endpoints(client):
    customers = client.get("/api/customers").json()
    assert len(customers) == 20
    assert {"ltv", "churn_risk", "renewal_days"} <= set(customers[0])

    client.post("/api/tickets", json=PASSWORD)
    stats = client.get("/api/stats").json()
    assert stats["total_tickets"] > 0
    assert 0.0 < stats["deflection_rate"] <= 1.0
    assert stats["override_rate"] >= 0.0

    res = client.post("/api/admin/rescore").json()
    assert res["status"] == "ok"


def test_listing_is_read_only_and_sorted(client):
    client.post("/api/tickets", json={"customer_id": "c2", "body": "Production API is down for all users"})
    items = client.get("/api/tickets?sort=priority").json()
    for a, b in zip(items, items[1:]):
        assert a["priority"] >= b["priority"]
    fcfs = client.get("/api/tickets?sort=fcfs").json()
    assert [t["created_at"] for t in fcfs] == sorted(t["created_at"] for t in fcfs)


def test_kb_test_match_validates_input(client):
    assert client.post("/api/kb/test-match", json={"text": ""}).status_code == 422
    assert client.post("/api/kb/test-match", json={"text": 123}).status_code == 422
    res = client.post("/api/kb/test-match", json={"text": "how do I reset my password"}).json()
    assert res["article_id"] == "kb_pass_01" and res["action"] == "auto_reply"


def test_what_if_preview_changes_nothing(client):
    client.post("/api/tickets", json={"customer_id": "c1", "body": "Our checkout is broken, losing money every hour"})
    before = client.get("/api/tickets").json()
    res = client.post("/api/whatif", json={"weights": {"value": 0.9, "urgency": 0.05, "frustration": 0.05, "age": 0.0},
                                           "senior_score": 30}).json()
    assert abs(sum(res["weights"].values()) - 1.0) < 0.01
    assert len(res["tickets"]) == sum(1 for t in before if t["status"] in ("queued", "in_progress"))
    after = client.get("/api/tickets").json()
    assert [(t["id"], t["priority"], t["route"]) for t in after] == [(t["id"], t["priority"], t["route"]) for t in before]


def test_config_exposes_tuned_values(client):
    cfg = client.get("/api/config").json()
    assert abs(sum(cfg["weights"].values()) - 1.0) < 1e-9
    assert cfg["frustration_model"]["kind"] in ("logistic", "playbook_linear")
    assert 0 < cfg["frustration_senior"] < 1
