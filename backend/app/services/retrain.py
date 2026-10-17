"""Learning from agents: when agents re-route tickets (admin overrides, agent escalations), those
decisions are labels for where a ticket *should* have gone. Retraining searches the routing
thresholds that best agree with them. It refuses to run on too few decisions, because a
handful of examples would just overfit."""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Feedback, Ticket
from app.services.priority import compute_priority
from app.services.router import decide, frustration_threshold
from app.services.triage import _explanation, flags_of

MIN_DECISIONS = 30
TUNING_FILE = Path(__file__).resolve().parents[2] / "data" / "router_tuning.json"


def load_tuning() -> None:
    """Apply previously accepted retraining results at startup."""
    try:
        data = json.loads(TUNING_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    settings.level3_score = int(data.get("level3_score", settings.level3_score))
    if data.get("frustration_senior") is not None:
        settings.frustration_senior = float(data["frustration_senior"])


def _labels(db: Session) -> list[tuple[Ticket, str]]:
    rows = (db.query(Feedback)
            .filter(Feedback.kind.in_(("override", "escalate")), Feedback.new_route.isnot(None))
            .order_by(Feedback.created_at).all())
    latest: dict[int, str] = {}
    for f in rows:
        if f.new_route in ("level1", "level2", "level3") and f.new_route != f.old_route:
            latest[f.ticket_id] = f.new_route
    out = []
    for tid, label in latest.items():
        t = db.get(Ticket, tid)
        if t:
            out.append((t, label))
    return out


def _agreement(pairs, level3_score: int, fr_th: float) -> float:
    hits = 0
    for t, label in pairs:
        pr = compute_priority(t.urgency, t.frustration, t.value, 0, t.sla_minutes, _explanation(t).get("static_boosts", {}))
        d = decide(pr.route_score, t.frustration, t.intent, flags_of(t), 0.0, value=t.value, allow_auto=False,
                   level3_score=level3_score, frustration_senior=fr_th, category=t.category)
        hits += d.route == label
    return hits / len(pairs) if pairs else 0.0


def propose(db: Session) -> dict:
    pairs = _labels(db)
    current = {"level3_score": settings.level3_score, "frustration_senior": round(frustration_threshold(), 2)}
    if len(pairs) < MIN_DECISIONS:
        return {"status": "insufficient", "decisions": len(pairs), "needed": MIN_DECISIONS, "current": current,
                "message": f"Only {len(pairs)} agent routing decisions so far; at least {MIN_DECISIONS} are needed "
                           "before retraining is meaningful."}
    before = _agreement(pairs, current["level3_score"], current["frustration_senior"])
    best = (before, current["level3_score"], current["frustration_senior"])
    for l3 in range(50, 86, 5):
        for fr in [x / 100 for x in range(30, 81, 5)]:
            a = _agreement(pairs, l3, fr)
            if a > best[0] + 1e-9:
                best = (a, l3, fr)
    return {
        "status": "ok", "decisions": len(pairs), "current": current,
        "proposed": {"level3_score": best[1], "frustration_senior": best[2]},
        "agreement_before": round(before, 3), "agreement_after": round(best[0], 3),
        "message": "Agreement = how often the router would have made the same call as your agents.",
    }


def apply(level3_score: int, frustration_senior: float) -> dict:
    settings.level3_score = level3_score
    settings.frustration_senior = frustration_senior
    TUNING_FILE.write_text(json.dumps({"level3_score": level3_score, "frustration_senior": frustration_senior},
                                      indent=2), encoding="utf-8")
    return {"level3_score": level3_score, "frustration_senior": frustration_senior}
