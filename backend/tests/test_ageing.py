from datetime import datetime, timedelta, timezone
from app.db import SessionLocal
from app.models import Customer, Ticket
from app.services.rescore import rescore_open


def test_ageing_increases_score_and_upgrades_route():
    db = SessionLocal()
    try:
        # Create a ticket in Tier 1 with moderate urgency, basic segment, 0 initial wait
        now = datetime.now(timezone.utc)
        cust = db.query(Customer).filter(Customer.segment == "pro").first()

        ticket = Ticket(
            customer_id=cust.id if cust else None,
            subject="Billing question",
            body="I have a question about my invoice",
            created_at=now,
            status="queued",
            urgency=0.55,
            frustration=0.20,
            value=0.75,  # valuable account: once ageing lifts the score past 50 it escalates
            intent="invoice",
            priority=32,  # Starts in Level 1
            route="level1",
            route_reason="Routine request",
            route_locked=False,
            kb_confidence=0.1,
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        initial_score = ticket.priority
        initial_route = ticket.route

        # Advance simulated time by 180 minutes (3 hours of waiting)
        future_time = now + timedelta(minutes=180)
        rescore_open(db, now=future_time)
        db.refresh(ticket)

        # Priority must strictly increase
        assert ticket.priority > initial_score
        # Valuable, waiting ticket: ageing lifts it past the Level 3 score
        assert ticket.route == "level3"
        assert ticket.route_reason.startswith("Waited too long")
        assert ticket.assigned_agent_id is not None  # re-assigned to a Level 3 agent

        # Verify anti-starvation: running with past time never downgrades priority or route
        past_time = now - timedelta(minutes=60)
        score_before_past = ticket.priority
        rescore_open(db, now=past_time)
        db.refresh(ticket)
        assert ticket.priority == score_before_past
        assert ticket.route == "level3"

    finally:
        db.close()


def test_locked_route_cannot_be_changed_by_ageing():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        ticket = Ticket(
            customer_id=None,
            subject="Special handling",
            body="Agent manually set this to tier1 and locked",
            created_at=now - timedelta(minutes=300),
            status="queued",
            urgency=0.8,
            frustration=0.5,
            value=0.3,
            intent="other",
            priority=50,
            route="level1",
            route_reason="Agent override: keeping in level 1 for investigation",
            route_locked=True,  # LOCKED!
            kb_confidence=0.0,
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        # Rescore
        rescore_open(db, now=now)
        db.refresh(ticket)

        # Priority may rise, but route MUST remain level1 because route_locked is True
        assert ticket.route == "level1"
        assert "Agent override" in ticket.route_reason

    finally:
        db.close()
