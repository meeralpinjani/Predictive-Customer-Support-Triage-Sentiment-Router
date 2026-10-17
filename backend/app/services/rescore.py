from datetime import datetime, timezone
import logging
from sqlalchemy.orm import Session

from app.models import Ticket
from app.services.router import LEVEL, Decision, decide
from app.services.triage import OPEN, route_ticket, score_ticket, store_priority

log = logging.getLogger("triage.rescore")


def rescore_open(db: Session, now: datetime | None = None) -> int:
    """Re-score waiting tickets so priority rises with age (anti-starvation).

    - Priority never drops through ageing; a priority set by an agent is never touched.
    - Routes only move up, never into auto-answer, and never when an agent locked them.
    """
    now = now or datetime.now(timezone.utc)
    open_tickets = db.query(Ticket).filter(Ticket.status.in_(OPEN)).all()

    for t in open_tickets:
        pr = score_ticket(t, now)
        if not t.priority_locked:
            t.priority = max(t.priority, pr.score)
        store_priority(t, pr)

        if not t.route_locked:
            flags = [f for f in t.critical_flags.split(",") if f]
            d = decide(pr.route_score, t.frustration, t.intent, flags, t.kb_confidence,
                       value=t.value, allow_auto=False, mode=t.analysis_mode)
            if d.route in LEVEL and t.route in LEVEL and LEVEL[d.route] > LEVEL[t.route]:
                route_ticket(db, t, Decision(d.route, "Ageing upgrade", t.kb_action))

    db.commit()
    return len(open_tickets)
