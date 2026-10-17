"""Incidents: one underlying problem reported in several tickets (e.g. an outage). The system
suggests groups of near-duplicate open tickets; an agent confirms, then replies to or resolves
all of them at once."""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Customer, Incident, Ticket, User
from app.services.similarity import DUPLICATE_THRESHOLD, cluster
from app.services.triage import OPEN, add_system_message, agent_reply


def visible_open_tickets(db: Session, user: User, hours: int = 24) -> list[Ticket]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = db.query(Ticket).filter(Ticket.status.in_(OPEN), Ticket.incident_id.is_(None), Ticket.created_at >= since)
    if user.role != "admin":
        q = q.filter((Ticket.route == user.role) | (Ticket.assigned_agent_id == user.id))
    return q.order_by(Ticket.priority.desc()).all()


def suggestions(db: Session, user: User) -> dict:
    tickets = visible_open_tickets(db, user)
    texts = [f"{t.subject}. {t.body}" if t.subject else t.body for t in tickets]
    groups, method = cluster(texts, DUPLICATE_THRESHOLD, min_size=2)
    out = []
    for g in groups:
        members = [tickets[i] for i in g]
        lead = members[0]
        out.append({
            "title": (lead.subject or lead.body)[:80],
            "ticket_ids": [t.id for t in members],
            "customers": sorted({(db.get(Customer, t.customer_id).name if t.customer_id else "Unknown") for t in members}),
            "examples": [(t.subject or t.body)[:120] for t in members[:4]],
            "top_priority": max(t.priority for t in members),
        })
    return {"method": method, "groups": out}


def create(db: Session, user: User, ticket_ids: list[int], title: str) -> Incident:
    inc = Incident(title=title, created_by_id=user.id)
    db.add(inc)
    db.flush()
    for t in db.query(Ticket).filter(Ticket.id.in_(ticket_ids)).all():
        t.incident_id = inc.id
        add_system_message(db, t, f"Linked to incident #{inc.id}: {title}. Updates for everyone affected will appear here.")
    db.commit()
    db.refresh(inc)
    return inc


def linked(db: Session, inc: Incident) -> list[Ticket]:
    return db.query(Ticket).filter(Ticket.incident_id == inc.id).order_by(Ticket.priority.desc()).all()


def reply_all(db: Session, inc: Incident, user: User, body: str) -> list[Ticket]:
    targets = [t for t in linked(db, inc) if t.status in OPEN]
    for t in targets:
        agent_reply(db, t, user, body)
    db.commit()
    return targets


def resolve(db: Session, inc: Incident, user: User, note: str) -> list[Ticket]:
    now = datetime.now(timezone.utc)
    targets = [t for t in linked(db, inc) if t.status != "resolved"]
    for t in targets:
        if note:
            agent_reply(db, t, user, note)
        t.status, t.resolved_at = "resolved", now
        add_system_message(db, t, f"Resolved with incident #{inc.id}.")
    inc.status, inc.resolved_at = "resolved", now
    db.commit()
    return targets
