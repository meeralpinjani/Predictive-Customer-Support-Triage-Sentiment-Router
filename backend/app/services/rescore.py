from datetime import datetime, timezone
import json
import logging
from sqlalchemy.orm import Session

from app.config import DEFAULT_SLA_MIN
from app.models import Customer, Ticket
from app.services.priority import compute_priority
from app.services.router import LEVEL, decide
from app.services.triage import ensure_utc

log = logging.getLogger("triage.rescore")


def rescore_open(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    open_tickets = (
        db.query(Ticket)
        .filter(Ticket.status.in_(["queued", "in_progress"]))
        .all()
    )
    rescored_count = 0

    for t in open_tickets:
        cust = db.get(Customer, t.customer_id) if t.customer_id else None
        sla = cust.sla_minutes if cust else DEFAULT_SLA_MIN
        created_utc = ensure_utc(t.created_at)
        wait_min = max((now - created_utc).total_seconds() / 60.0, 0.0)

        pr = compute_priority(t.urgency, t.frustration, t.value, wait_min, sla)

        # Anti-starvation: priority can only stay same or rise due to ageing
        t.priority = max(t.priority, pr.score)

        # Route updates
        if not t.route_locked:
            flags = [f for f in t.critical_flags.split(",") if f]
            d = decide(pr.score, t.frustration, t.intent, flags, t.kb_confidence)

            # Ageing can upgrade a route, never downgrade
            if d.route in LEVEL and t.route in LEVEL:
                if LEVEL[d.route] > LEVEL[t.route]:
                    t.route = d.route
                    t.route_reason = "Ageing upgrade"

        # Update explanation json
        try:
            expl = json.loads(t.explanation_json)
        except Exception:
            expl = {}
        expl["components"] = pr.components
        expl["contributions"] = pr.contributions
        expl["reasons"] = pr.reasons
        t.explanation_json = json.dumps(expl)

        rescored_count += 1

    db.commit()
    return rescored_count
