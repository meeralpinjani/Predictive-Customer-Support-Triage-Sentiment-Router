"""Attachments, search, knowledge base, suggested replies, availability, incidents, analytics,
retraining and password recovery."""
import re

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n" + b"0" * 64


def new_ticket(c, category="howto", body="How do I schedule weekly report emails?"):
    res = c.post("/api/tickets", json={"category": category, "body": body})
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------- attachments
def test_attachments_are_validated_and_private(login):
    priya, elena = login("priya"), login("elena")
    t = new_ticket(priya, "bug", "The export page shows an error.")
    up = priya.post(f"/api/tickets/{t['id']}/attachments",
                    files=[("files", ("screen.png", PNG, "image/png")), ("files", ("log.pdf", PDF, "application/pdf"))])
    assert up.status_code == 201
    a = up.json()
    assert {x["content_type"] for x in a} == {"image/png", "application/pdf"}

    # Only allowed bytes: a renamed text file or an SVG is refused whatever the extension says.
    bad = priya.post(f"/api/tickets/{t['id']}/attachments", files=[("files", ("evil.png", b"<svg onload=alert(1)>", "image/png"))])
    assert bad.status_code == 415
    big = priya.post(f"/api/tickets/{t['id']}/attachments", files=[("files", ("big.png", PNG + b"0" * (5 * 1024 * 1024), "image/png"))])
    assert big.status_code == 413
    six = priya.post(f"/api/tickets/{t['id']}/attachments", files=[("files", (f"{i}.png", PNG, "image/png")) for i in range(6)])
    assert six.status_code == 400

    url = a[0]["url"]
    assert priya.get(url).content == PNG
    assert priya.get(url).headers["x-content-type-options"] == "nosniff"
    assert elena.get(url).status_code == 404                      # another customer can't open it
    assert login(t["route"]).get(url).status_code == 200          # the agent handling it can
    assert len(priya.get(f"/api/my/tickets/{t['id']}").json()["attachments"]) == 2


def test_chat_message_with_screenshot(login):
    priya = login("priya")
    t = new_ticket(priya, "bug", "Reports page crashes on load.")
    res = priya.post(f"/api/tickets/{t['id']}/messages/upload", data={"body": "Here is the screenshot"},
                     files=[("files", ("crash.png", PNG, "image/png"))])
    assert res.status_code == 201
    msg = res.json()
    assert msg["body"] == "Here is the screenshot" and msg["attachments"][0]["is_image"]
    agent = login(t["route"])
    msgs = agent.get(f"/api/tickets/{t['id']}/messages").json()
    assert any(m["attachments"] for m in msgs)


# ---------------------------------------------------------------- search & knowledge base
def test_search_is_scoped_by_role(login):
    priya, elena = login("priya"), login("elena")
    t = new_ticket(priya, "billing", "Unusual zebra charge on my invoice")
    assert any(x["id"] == t["id"] for x in priya.get("/api/search", params={"q": "zebra"}).json()["tickets"])
    assert elena.get("/api/search", params={"q": "zebra"}).json()["tickets"] == []
    res = elena.get("/api/search", params={"q": "reset password"}).json()
    assert res["articles"] and all(a["visibility"] == "public" for a in res["articles"])
    assert "customers" not in res and "users" not in res

    admin = login("admin").get("/api/search", params={"q": "Northwind"}).json()
    assert any(c["name"] == "Northwind Logistics" for c in admin["customers"])
    assert "users" in admin
    agent = login("level3").get("/api/search", params={"q": "security incident"}).json()
    assert any(a["visibility"] == "internal" for a in agent["articles"])   # agents find internal guides


def test_internal_guides_are_hidden_from_customers(login):
    cust = login("elena").get("/api/kb-articles").json()
    staff = login("level1").get("/api/kb-articles").json()
    assert all(a["visibility"] == "public" for a in cust)
    assert any(a["visibility"] == "internal" for a in staff)


def test_articles_suggested_while_typing(login):
    res = login("elena").get("/api/kb/suggest", params={"q": "I forgot my password, how do I reset it?"}).json()
    assert res and res[0]["id"] == "kb_pass_01"
    assert login("elena").get("/api/kb/suggest", params={"q": "hi"}).json() == []


def test_guides_follow_the_ticket(login):
    t = new_ticket(login("elena"), "account", "Someone hacked my account and changed my email!")
    guides = login("level3").get(f"/api/tickets/{t['id']}/guides").json()
    assert guides[0]["id"] == "guide_security"


def test_admin_kb_editor_and_auto_answer_index(login):
    admin = login("admin")
    a = admin.post("/api/kb-articles", json={
        "title": "Exporting invoices to Xero", "answer": "Go to Billing > Integrations > Xero and click Connect.",
        "questions": ["how do I export invoices to xero", "connect xero"], "visibility": "public"}).json()
    match = admin.post("/api/kb/test-match", json={"text": "how do I export invoices to xero"}).json()
    assert match["article_id"] == a["id"]                       # new article answers right away
    admin.patch(f"/api/kb-articles/{a['id']}", json={**{k: a[k] for k in ("title", "answer", "questions")},
                                                     "visibility": "internal", "tags": ["billing"]})
    assert admin.post("/api/kb/test-match", json={"text": "how do I export invoices to xero"}).json().get("article_id") != a["id"]
    assert admin.delete(f"/api/kb-articles/{a['id']}").json()["ok"]
    assert login("level1").post("/api/kb-articles", json={"title": "x" * 5, "answer": "y" * 20}).status_code == 403
    assert "topics" in admin.get("/api/kb/topics").json()


# ---------------------------------------------------------------- suggested reply
def test_suggested_reply_matches_tone(login):
    calm = new_ticket(login("elena"), "billing", "Where can I download last month's invoice?")
    angry = new_ticket(login("elena"), "bug", "This is RIDICULOUS!!! The export is broken AGAIN, I'm furious and fed up.")
    if calm["route"] != "auto_kb":
        r = login(calm["route"]).get(f"/api/tickets/{calm['id']}/suggested-reply").json()
        assert r["tone"] in ("low", "medium") and r["text"].startswith("Hi Elena,")
    r2 = login(angry["route"]).get(f"/api/tickets/{angry['id']}/suggested-reply").json()
    assert r2["tone"] == "high" and "sorry" in r2["text"].lower()
    assert login("elena").get(f"/api/tickets/{angry['id']}/suggested-reply").status_code == 403


# ---------------------------------------------------------------- availability & capacity
def test_offline_agents_get_no_tickets_and_queue_rebalances(login):
    l1 = login("level1")
    me = l1.get("/api/auth/me").json()
    assert l1.patch("/api/auth/me/availability", json={"availability": "offline"}).json()["availability"] == "offline"
    t = new_ticket(login("elena"), "feedback", "Please add a dark theme to the mobile app.")
    if t["route"] == "level1":
        assert login("admin").get(f"/api/tickets/{t['id']}").json()["assigned_agent"] is None
    l1.patch("/api/auth/me/availability", json={"availability": "available"})
    if t["route"] == "level1":
        assert login("admin").get(f"/api/tickets/{t['id']}").json()["assigned_agent"]["id"] == me["id"]
    work = login("admin").get("/api/admin/users/workload/summary").json()
    assert any(w["name"] == me["name"] and "max_open" in w for w in work)
    assert login("elena").patch("/api/auth/me/availability", json={"availability": "busy"}).status_code == 403


def test_capacity_limit(login):
    admin = login("admin")
    l2 = next(u for u in admin.get("/api/admin/users").json() if u["email"] == "level2@triage.demo")
    admin.patch(f"/api/admin/users/{l2['id']}", json={"max_open": 0})
    t = new_ticket(login("elena"), "bug", "The calendar widget crashes in Safari.")
    assert t["route"] == "level2"
    assert admin.get(f"/api/tickets/{t['id']}").json()["assigned_agent"] is None   # full: waits in queue
    admin.patch(f"/api/admin/users/{l2['id']}", json={"max_open": 8})
    assert admin.get(f"/api/tickets/{t['id']}").json()["assigned_agent"]["id"] == l2["id"]


# ---------------------------------------------------------------- incidents
def test_incident_grouping_reply_and_resolve(login):
    admin = login("admin")
    ids = []
    for cid in ("c3", "c5", "c7"):
        r = admin.post("/api/tickets", json={"customer_id": cid, "category": "integrations",
                                             "body": "Webhook deliveries to our Slack channel stopped arriving this morning."})
        ids.append(r.json()["id"])
    groups = admin.get("/api/incidents/suggestions").json()["groups"]
    assert any(set(ids) <= set(g["ticket_ids"]) for g in groups)
    inc = admin.post("/api/incidents", json={"ticket_ids": ids, "title": "Slack webhooks down"}).json()
    assert inc["open"] == 3
    assert admin.post("/api/incidents", json={"ticket_ids": ids[:2], "title": "dup"}).status_code == 409
    rep = admin.post(f"/api/incidents/{inc['id']}/reply", json={"body": "We're on it, update in 30 minutes."}).json()
    assert rep["replied_to"] == 3
    done = admin.post(f"/api/incidents/{inc['id']}/resolve", json={"body": "Fixed: deliveries resumed."}).json()
    assert done["status"] == "resolved" and done["open"] == 0
    assert admin.get(f"/api/tickets/{ids[0]}").json()["incident"]["id"] == inc["id"]


# ---------------------------------------------------------------- analytics & retraining
def test_analytics_comes_from_the_database(login):
    admin = login("admin")
    before = admin.get("/api/admin/analytics").json()
    new_ticket(login("elena"), "howto", "How do I add a teammate to my workspace?")
    after = admin.get("/api/admin/analytics").json()
    assert len(after["hourly"]) == 24 and len(after["daily"]) == 7
    assert sum(h["total"] for h in after["hourly"]) == sum(h["total"] for h in before["hourly"]) + 1
    assert login("level1").get("/api/admin/analytics").status_code == 403


def test_retrain_refuses_without_enough_decisions(login):
    res = login("admin").get("/api/admin/retrain").json()
    assert res["status"] == "insufficient" and res["needed"] == 30
    assert login("admin").post("/api/admin/retrain/apply",
                               json={"level3_score": 60, "frustration_senior": 0.5}).status_code == 409


# ---------------------------------------------------------------- password reset
def test_recovery_code_resets_password(anon, login):
    res = anon.post("/api/auth/signup", json={"name": "Code User", "email": "codeuser@example.com", "password": "Original1"})
    code = res.json()["recovery_code"]
    assert re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", code)
    assert anon.get("/api/auth/me").json()["recovery_code"] is None          # shown once, never again
    assert anon.get("/api/auth/me").json()["has_recovery_code"] is True

    wrong = anon.post("/api/auth/recover", json={"email": "codeuser@example.com", "code": "AAAA-BBBB-CCCC", "password": "BrandNew2"})
    assert wrong.status_code == 401
    ok = anon.post("/api/auth/recover", json={"email": "codeuser@example.com", "code": code.lower().replace("-", " "),
                                              "password": "BrandNew2"}).json()
    assert ok["ok"] and ok["recovery_code"] != code                          # a fresh code replaces the used one
    again = anon.post("/api/auth/recover", json={"email": "codeuser@example.com", "code": code, "password": "BrandNew3"})
    assert again.status_code == 401                                          # old code is used up
    assert anon.post("/api/auth/login", json={"email": "codeuser@example.com", "password": "BrandNew2"}).status_code == 200


def test_regenerate_code_needs_current_password(anon):
    anon.post("/api/auth/signup", json={"name": "Regen", "email": "regen@example.com", "password": "Original1"})
    assert anon.post("/api/auth/me/recovery-code", json={"current_password": "nope"}).status_code == 401
    assert anon.post("/api/auth/me/recovery-code", json={"current_password": "Original1"}).json()["recovery_code"]


def test_admin_reset_link_fallback(anon, login):
    anon.post("/api/auth/signup", json={"name": "Lost Code", "email": "lostcode@example.com", "password": "Original1"})
    res = anon.post("/api/auth/forgot", json={"email": "lostcode@example.com"}).json()
    # Same answer for unknown emails (no account probing).
    assert anon.post("/api/auth/forgot", json={"email": "nobody@example.com"}).json()["message"] == res["message"]

    admin = login("admin")
    user = next(u for u in admin.get("/api/admin/users").json() if u["email"] == "lostcode@example.com")
    assert user["reset_requested_at"] is not None                            # admin sees the request
    link = admin.post(f"/api/admin/users/{user['id']}/reset-link").json()
    token = link["path"].split("token=")[1]
    assert login("level1").post(f"/api/admin/users/{user['id']}/reset-link").status_code == 403

    assert anon.post("/api/auth/reset", json={"token": token, "password": "weak"}).status_code == 422
    assert anon.post("/api/auth/reset", json={"token": token, "password": "BrandNew2"}).json()["ok"]
    assert anon.post("/api/auth/reset", json={"token": token, "password": "BrandNew3"}).status_code == 400  # one use
    assert anon.post("/api/auth/login", json={"email": "lostcode@example.com", "password": "BrandNew2"}).status_code == 200
    after = next(u for u in admin.get("/api/admin/users").json() if u["email"] == "lostcode@example.com")
    assert after["reset_requested_at"] is None


def test_remember_me_controls_cookie_lifetime(anon):
    anon.post("/api/auth/signup", json={"name": "Rem", "email": "rem@example.com", "password": "Remember1"})
    short = anon.post("/api/auth/login", json={"email": "rem@example.com", "password": "Remember1", "remember": False})
    assert "max-age" not in short.headers["set-cookie"].lower()
    long = anon.post("/api/auth/login", json={"email": "rem@example.com", "password": "Remember1", "remember": True})
    assert "max-age" in long.headers["set-cookie"].lower()


def test_password_policy(anon):
    weak = anon.post("/api/auth/signup", json={"name": "W", "email": "weak@example.com", "password": "alllowercase1"})
    assert weak.status_code == 422
