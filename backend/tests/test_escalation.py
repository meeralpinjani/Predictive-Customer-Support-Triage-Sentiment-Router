"""Live escalation paths, conversation and Level 3 callbacks."""
from app import events


def new_ticket(c, category, body):
    res = c.post("/api/tickets", json={"category": category, "body": body})
    assert res.status_code == 201, res.text
    return res.json()


def test_category_sets_the_starting_level(login):
    c = login("elena")
    assert new_ticket(c, "feedback", "Please add keyboard shortcuts to the editor.")["route"] == "level1"
    assert new_ticket(c, "integrations", "Our webhook deliveries stopped arriving.")["route"] == "level2"


def test_ai_escalates_above_the_category_but_never_below(login):
    c = login("elena")
    # Picked "General" but it's a security incident -> Level 3.
    assert new_ticket(c, "account", "Someone hacked my account and changed the email!")["route"] == "level3"
    # Picked "General" but it's clearly broken -> Technical Support.
    assert new_ticket(c, "howto", "The reports page crashes with an error every time.")["route"] == "level2"


def test_agent_escalates_one_level_at_a_time(login):
    t = new_ticket(login("elena"), "howto", "How do I schedule weekly report emails?")
    assert t["route"] == "level1"
    l1 = login("level1")
    res = l1.post(f"/api/tickets/{t['id']}/escalate", json={"reason": "Needs a technical look"}).json()
    assert res["route"] == "level2" and res["assigned_agent"]["level"] == "level2"
    assert l1.get(f"/api/tickets/{t['id']}").status_code == 404     # left Level 1's view
    l2 = login("level2")
    assert l2.post(f"/api/tickets/{t['id']}/escalate", json={"reason": "Expert needed"}).json()["route"] == "level3"
    assert login("level3").post(f"/api/tickets/{t['id']}/escalate", json={"reason": "more"}).status_code == 409


def test_angrier_customer_reply_escalates_live(login):
    cust = login("elena")
    t = new_ticket(cust, "howto", "How do I change the time zone on tickets?")
    tid = t["id"]
    if t["route"] == "auto_kb":   # the KB may answer it; replying reopens it to a human
        assert t["auto_reply"]
    res = cust.post(f"/api/tickets/{tid}/messages",
                    json={"body": "This is RIDICULOUS!!! Third time asking, I'm furious and fed up. Fix it NOW!"})
    assert res.status_code == 201
    after = cust.get(f"/api/my/tickets/{tid}").json()
    assert after["route"] == "level3" and after["live_chat"] is True
    msgs = cust.get(f"/api/tickets/{tid}/messages").json()
    assert any("frustration rising" in m["body"] for m in msgs if m["kind"] == "system")
    assert all(m["frustration"] is None for m in msgs)               # customers never see scores


def test_kb_not_helpful_goes_to_a_human(login):
    cust = login("elena")
    t = new_ticket(cust, "account", "Resetting Your Account Password. How do I reset my password?")
    assert t["route"] == "auto_kb" and t["status"] == "kb_handled"
    res = cust.post(f"/api/tickets/{t['id']}/feedback", json={"kind": "kb_not_helpful"}).json()
    assert res["status"] == "queued" and res["route"] in ("level1", "level2", "level3")
    assert cust.post(f"/api/tickets/{t['id']}/feedback", json={"kind": "kb_helpful"}).status_code == 409


def test_conversation_between_customer_and_agent(login):
    cust = login("priya")
    t = new_ticket(cust, "billing", "Can you explain the extra line on my invoice?")
    agent = login(t["route"]) if t["route"] != "auto_kb" else login("level1")
    if t["route"] == "auto_kb":
        cust.post(f"/api/tickets/{t['id']}/messages", json={"body": "That didn't answer it, sorry."})
        agent = login(cust.get(f"/api/my/tickets/{t['id']}").json()["route"])
    r = agent.post(f"/api/tickets/{t['id']}/messages", json={"body": "Happy to help, checking now."})
    assert r.status_code == 201
    assert agent.get(f"/api/tickets/{t['id']}").json()["status"] == "in_progress"   # replying claims it
    msgs = cust.get(f"/api/tickets/{t['id']}/messages").json()
    agent_msg = next(m for m in msgs if m["body"] == "Happy to help, checking now.")
    assert len(agent_msg["author_name"].split()) == 1      # customers see the agent's first name only
    assert cust.post(f"/api/tickets/{t['id']}/resolve").json()["status"] == "resolved"


def test_callbacks_only_at_level3(login):
    cust = login("elena")
    low = new_ticket(cust, "feedback", "A dark theme for the editor would be lovely.")
    assert cust.post(f"/api/tickets/{low['id']}/callbacks", json={"phone": "+46 70 123 45 67"}).status_code == 409
    high = new_ticket(cust, "account", "Someone accessed my account and stole data from our workspace!")
    assert high["route"] == "level3"
    cb = cust.post(f"/api/tickets/{high['id']}/callbacks",
                   json={"phone": "+46 70 123 45 67", "preferred_time": "Today 15:00"})
    assert cb.status_code == 201
    assert cust.post(f"/api/tickets/{high['id']}/callbacks", json={"phone": "+46 70 000 00 00"}).status_code == 409
    expert = login("level3")
    upd = expert.patch(f"/api/tickets/{high['id']}/callbacks/{cb.json()['id']}", json={"status": "scheduled"})
    assert upd.json()["status"] == "scheduled"
    assert login("level1").patch(f"/api/tickets/{high['id']}/callbacks/{cb.json()['id']}",
                                 json={"status": "done"}).status_code == 403


def test_event_routing_rules():
    def sub(role, uid=1, cust=None):
        return events.Subscriber(uid, role, cust)
    ev = {"type": "ticket.escalated", "route": "level2", "old_route": "level1", "customer_id": "c9", "assigned_agent_id": 7}
    assert events._wants(sub("admin"), ev)
    assert events._wants(sub("level1"), ev) and events._wants(sub("level2"), ev)   # it left / it arrived
    assert not events._wants(sub("level3"), ev)
    assert events._wants(sub("customer", cust="c9"), ev)
    assert not events._wants(sub("customer", cust="c1"), ev)
    typing = {**ev, "type": "typing", "actor_id": 1}
    assert not events._wants(sub("admin", uid=1), typing)   # no echo of your own typing


def test_subscribe_publish_delivers_filtered_events():
    import asyncio

    async def run():
        events.bind_loop(asyncio.get_running_loop())
        agent = events.subscribe(1, "level2", None)
        other = events.subscribe(2, "level1", None)
        try:
            events.publish({"type": "ticket.created", "route": "level2", "old_route": None,
                            "customer_id": "c9", "assigned_agent_id": None, "ticket_id": 5})
            await asyncio.sleep(0)
            assert (await asyncio.wait_for(agent.queue.get(), 1))["ticket_id"] == 5
            assert other.queue.empty()
        finally:
            events.unsubscribe(agent)
            events.unsubscribe(other)

    asyncio.run(run())
