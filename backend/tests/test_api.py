PASSWORD = {
    "customer_id": "c9",
    "category": "account",
    "subject": "Resetting Your Account Password",
    "body": "How do I reset my password? Forgot my password what should I do?",
}


def test_post_then_get_flow(client):
    created = client.post("/api/tickets", json={
        "customer_id": "c3", "category": "billing", "subject": "Double invoice dispute",
        "body": "I was charged twice this month. Please refund today.",
    })
    assert created.status_code == 201
    t = created.json()
    assert t["assigned_agent"]["level"] == t["route"]
    assert t["level_name"].startswith("Level")
    got = client.get(f"/api/tickets/{t['id']}")
    assert got.status_code == 200 and got.json()["id"] == t["id"]
    msgs = client.get(f"/api/tickets/{t['id']}/messages").json()
    assert msgs[0]["kind"] == "system" and "Routed to" in msgs[0]["body"]


def test_404_on_missing_ticket(client):
    assert client.get("/api/tickets/9999999").status_code == 404


def test_unknown_customer_and_category_are_rejected(client):
    assert client.post("/api/tickets", json={"customer_id": "nope", "category": "howto", "body": "Hi"}).status_code == 404
    assert client.post("/api/tickets", json={"category": "astrology", "body": "Hi"}).status_code == 422


def test_422_on_invalid_input(client):
    assert client.post("/api/tickets", json={"category": "howto", "body": ""}).status_code == 422
    assert client.post("/api/tickets", json={"category": "howto", "body": "x", "channel": "fax"}).status_code == 422


def test_override_requires_reason_and_locks(client):
    t = client.post("/api/tickets", json={"customer_id": "c9", "category": "howto", "body": "How do I change my nickname?"}).json()
    assert client.post(f"/api/tickets/{t['id']}/override", json={"route": "level3", "reason": "no"}).status_code == 422
    assert client.post(f"/api/tickets/{t['id']}/override", json={"reason": "nothing to change"}).status_code == 422
    res = client.post(f"/api/tickets/{t['id']}/override",
                      json={"route": "level3", "priority": 85, "reason": "Escalating per executive request"}).json()
    assert res["route"] == "level3" and res["priority"] == 85
    assert res["route_locked"] is True and res["priority_locked"] is True
    assert "Admin override" in res["route_reason"]
    assert res["assigned_agent"]["level"] == "level3"


def test_admin_lowered_priority_survives_rescore(client):
    t = client.post("/api/tickets", json={"customer_id": "c1", "category": "outage", "body": "Our production website is down!"}).json()
    client.post(f"/api/tickets/{t['id']}/override", json={"priority": 5, "reason": "Known incident, tracked elsewhere"})
    client.post("/api/admin/rescore")
    assert client.get(f"/api/tickets/{t['id']}").json()["priority"] == 5


def test_resolve_is_one_way(client):
    t = client.post("/api/tickets", json={"category": "howto", "body": "Need quick help"}).json()
    first = client.post(f"/api/tickets/{t['id']}/resolve")
    assert first.status_code == 200 and first.json()["status"] == "resolved"
    assert client.post(f"/api/tickets/{t['id']}/resolve").status_code == 409
    assert client.post(f"/api/tickets/{t['id']}/override", json={"route": "level2", "reason": "too late"}).status_code == 409


def test_stats_and_rescore(client):
    client.post("/api/tickets", json=PASSWORD)
    stats = client.get("/api/stats").json()
    assert stats["total_tickets"] > 0
    assert 0.0 < stats["deflection_rate"] <= 1.0
    assert stats["agents_online"] == {"level1": 1, "level2": 1, "level3": 1} or sum(stats["agents_online"].values()) >= 3
    assert client.post("/api/admin/rescore").json()["status"] == "ok"
    assert len(client.get("/api/customers").json()) >= 20


def test_listing_is_sorted(client):
    client.post("/api/tickets", json={"customer_id": "c2", "category": "outage", "body": "Production API is down for all users"})
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
    client.post("/api/tickets", json={"customer_id": "c1", "category": "bug", "body": "Our checkout is broken, losing money every hour"})
    before = client.get("/api/tickets").json()
    res = client.post("/api/whatif", json={"weights": {"value": 0.9, "urgency": 0.05, "frustration": 0.05, "age": 0.0},
                                           "level3_score": 30}).json()
    assert abs(sum(res["weights"].values()) - 1.0) < 0.01
    assert len(res["tickets"]) == sum(1 for t in before if t["status"] in ("queued", "in_progress"))
    after = client.get("/api/tickets").json()
    assert [(t["id"], t["priority"], t["route"]) for t in after] == [(t["id"], t["priority"], t["route"]) for t in before]


def test_config_and_categories(client, anon):
    cfg = client.get("/api/config").json()
    assert abs(sum(cfg["weights"].values()) - 1.0) < 1e-9
    assert 0 < cfg["frustration_senior"] < 1
    cats = anon.get("/api/categories").json()
    assert {c["level"] for c in cats["categories"]} == {"level1", "level2"}   # Level 3 is never chosen
