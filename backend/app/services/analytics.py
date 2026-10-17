"""Analytics over time, computed only from what is in the database (nothing hard-coded)."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean

from sqlalchemy.orm import Session

from app.models import Message, Ticket
from app.services.triage import OPEN, ensure_utc


def _avg(xs: list[float]) -> float | None:
    return round(mean(xs), 1) if xs else None


def analytics(db: Session, days: int = 7) -> dict:
    now = datetime.now(timezone.utc)
    start_day = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    start_hour = (now - timedelta(hours=23)).replace(minute=0, second=0, microsecond=0)

    tickets = db.query(Ticket).filter(Ticket.created_at >= min(start_day, start_hour)).all()
    escalations = (db.query(Message)
                   .filter(Message.kind == "system", Message.body.like("Moved to %"), Message.created_at >= start_day)
                   .all())

    # ---- last 24 hours, per hour
    hourly = []
    buckets: dict[datetime, list[Ticket]] = defaultdict(list)
    for t in tickets:
        c = ensure_utc(t.created_at)
        if c >= start_hour:
            buckets[c.replace(minute=0, second=0, microsecond=0)].append(t)
    for i in range(24):
        h = start_hour + timedelta(hours=i)
        ts = buckets.get(h, [])
        hourly.append({
            "hour": h.isoformat(),
            "total": len(ts),
            "critical": sum(1 for t in ts if t.critical_flags),
            "auto": sum(1 for t in ts if t.route == "auto_kb"),
        })

    # ---- per day
    daily = []
    by_day: dict[str, list[Ticket]] = defaultdict(list)
    for t in tickets:
        c = ensure_utc(t.created_at)
        if c >= start_day:
            by_day[c.date().isoformat()].append(t)
    esc_by_day: dict[str, int] = defaultdict(int)
    for m in escalations:
        esc_by_day[ensure_utc(m.created_at).date().isoformat()] += 1
    resolved_by_day: dict[str, list[Ticket]] = defaultdict(list)
    for t in db.query(Ticket).filter(Ticket.resolved_at.isnot(None), Ticket.resolved_at >= start_day).all():
        resolved_by_day[ensure_utc(t.resolved_at).date().isoformat()].append(t)

    for i in range(days):
        d = (start_day + timedelta(days=i)).date().isoformat()
        ts = by_day.get(d, [])
        first = [(ensure_utc(t.first_response_at) - ensure_utc(t.created_at)).total_seconds() / 60
                 for t in ts if t.first_response_at]
        res = resolved_by_day.get(d, [])
        resolution = [(ensure_utc(t.resolved_at) - ensure_utc(t.created_at)).total_seconds() / 60 for t in res]
        auto = sum(1 for t in ts if t.route == "auto_kb")
        daily.append({
            "day": d,
            "created": len(ts),
            "auto_answered": auto,
            "deflection_rate": round(auto / len(ts), 3) if ts else None,
            "escalations": esc_by_day.get(d, 0),
            "resolved": len(res),
            "avg_first_response_min": _avg(first),
            "avg_resolution_min": _avg(resolution),
        })

    open_now = db.query(Ticket).filter(Ticket.status.in_(OPEN)).all()
    return {
        "generated_at": now.isoformat(),
        "days": days,
        "hourly": hourly,
        "daily": daily,
        "open_by_level": {lvl: sum(1 for t in open_now if t.route == lvl) for lvl in ("level1", "level2", "level3")},
        "data_since": min((ensure_utc(t.created_at) for t in db.query(Ticket).all()), default=now).isoformat(),
    }
