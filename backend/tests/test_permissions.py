"""Who can see and do what. These guard the loophole where anyone could act on any ticket."""


def new_ticket(c, category="howto", body="How do I change my nickname?"):
    res = c.post("/api/tickets", json={"category": category, "body": body})
    assert res.status_code == 201, res.text
    return res.json()


def test_anonymous_users_are_locked_out(anon):
    assert anon.get("/api/tickets").status_code == 401
    assert anon.post("/api/tickets", json={"category": "howto", "body": "hi"}).status_code == 401
    assert anon.get("/api/stats").status_code == 401
    assert anon.get("/api/health").status_code == 200   # public


def test_customers_only_see_their_own_tickets_without_scores(login):
    priya, elena = login("priya"), login("elena")
    t = new_ticket(priya, "billing", "I was charged twice this month.")
    assert "priority" not in t and "analysis" not in t          # no internal scores for customers
    assert any(x["id"] == t["id"] for x in priya.get("/api/my/tickets").json())
    assert all(x["id"] != t["id"] for x in elena.get("/api/my/tickets").json())
    assert elena.get(f"/api/my/tickets/{t['id']}").status_code == 404
    assert elena.get(f"/api/tickets/{t['id']}/messages").status_code == 404
    assert priya.get("/api/tickets").status_code == 403         # staff queue


def test_customer_cannot_pick_another_customer(login):
    t = login("elena").post("/api/tickets", json={"category": "howto", "body": "Hello there", "customer_id": "c1"}).json()
    assert t["id"]
    admin_view = login("admin").get(f"/api/tickets/{t['id']}").json()
    assert admin_view["customer"]["id"] == "c9"                  # their own CRM record, not Northwind


def test_agents_work_only_their_level(login):
    t = new_ticket(login("elena"), "bug", "The export button crashes the app.")
    assert t["route"] == "level2"
    l1, l2 = login("level1"), login("level2")
    assert all(x["id"] != t["id"] for x in l1.get("/api/tickets").json())
    assert any(x["id"] == t["id"] for x in l2.get("/api/tickets").json())
    assert l1.post(f"/api/tickets/{t['id']}/claim").status_code == 404
    assert l2.post(f"/api/tickets/{t['id']}/claim").json()["status"] == "in_progress"


def test_only_admins_override_and_see_insights(login):
    t = new_ticket(login("elena"))
    l1 = login("level1")
    assert l1.post(f"/api/tickets/{t['id']}/override", json={"route": "level3", "reason": "because"}).status_code == 403
    assert l1.get("/api/eval").status_code == 403
    assert l1.get("/api/admin/users").status_code == 403
    admin = login("admin")
    res = admin.post(f"/api/tickets/{t['id']}/override", json={"route": "level3", "priority": 90, "reason": "VIP request"})
    assert res.json()["route"] == "level3" and res.json()["route_locked"] and res.json()["priority_locked"]
