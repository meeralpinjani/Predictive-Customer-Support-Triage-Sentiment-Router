from datetime import datetime, timezone
import logging
from sqlalchemy.orm import Session

from app import events
from app.models import Ticket
from app.services.triage import OPEN, rebalance, rescore_and_route

log = logging.getLogger("triage.rescore")


def rescore_open(db: Session, now: datetime | None = None, publish: bool = True) -> int:
    """Re-score waiting tickets so priority rises with age (anti-starvation).

    - Priority never drops through ageing; a priority set by an admin is never touched.
    - Routes only move up (live escalation), never into auto-answer, never when locked.
    """
    now = now or datetime.now(timezone.utc)
    open_tickets = db.query(Ticket).filter(Ticket.status.in_(OPEN)).all()
    moved = []
    for t in open_tickets:
        old = rescore_and_route(db, t, "Ageing upgrade", now=now)
        if old != t.route:
            moved.append((t, old))
    for level in ("level1", "level2", "level3"):
        rebalance(db, level)   # agents who freed up capacity pick up waiting tickets
    db.commit()
    if publish:
        for t, old in moved:
            events.publish(events.ticket_event("ticket.escalated", t, old_route=old, reason=t.route_reason))
        if open_tickets:
            events.publish({"type": "queue.rescored", "route": None, "customer_id": None, "count": len(open_tickets)})
    return len(open_tickets)
