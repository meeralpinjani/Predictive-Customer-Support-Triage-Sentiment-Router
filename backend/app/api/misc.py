from datetime import datetime, timezone
from functools import lru_cache
import json
import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import WEIGHTS, settings
from app.db import get_db
from app.models import Customer, Feedback, KbArticle, Ticket
from app.nlp.kb import get_kb
from app.schemas import CustomerOut, HealthOut, StatsOut
from app.services.rescore import rescore_open
from app.services.triage import ensure_utc, load_kb_if_needed

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    try:
        kb_count = db.query(KbArticle).count()
    except Exception:
        kb_count = 0

    return HealthOut(
        status="ok" if db_status == "ok" else "degraded",
        nlp_mode=settings.nlp_mode,
        kb_size=kb_count,
        db=db_status,
    )


@router.get("/customers", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db)) -> list[CustomerOut]:
    return db.query(Customer).all()


@router.get("/kb-articles")
def list_kb_articles(db: Session = Depends(get_db)):
    articles = db.query(KbArticle).all()
    out = []
    for a in articles:
        try:
            qs = json.loads(a.questions) if a.questions.startswith("[") else [a.questions]
        except Exception:
            qs = [a.questions]
        out.append({
            "id": a.id,
            "title": a.title,
            "questions": qs,
            "answer": a.answer,
            "source": a.source,
        })
    return out


@router.post("/kb/test-match")
def test_kb_match(payload: dict, db: Session = Depends(get_db)):
    text = payload.get("text", "")
    kb_inst = get_kb(mode=settings.nlp_mode)
    if kb_inst is None:
        load_kb_if_needed(db)
        kb_inst = get_kb(mode=settings.nlp_mode)
    match = kb_inst.match(text) if kb_inst else None
    if not match:
        return {
            "matched": False,
            "confidence": 0.0,
            "action": "none",
            "suggest_threshold": settings.kb_suggest_threshold,
            "auto_threshold": settings.kb_auto_threshold,
        }
    action = (
        "auto_reply"
        if match.confidence >= settings.kb_auto_threshold
        else "suggest"
        if match.confidence >= settings.kb_suggest_threshold
        else "none"
    )
    return {
        "matched": True,
        "article_id": match.article_id,
        "title": match.title,
        "source": match.source,
        "answer": match.answer,
        "confidence": match.confidence,
        "action": action,
        "suggest_threshold": settings.kb_suggest_threshold,
        "auto_threshold": settings.kb_auto_threshold,
    }


@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)) -> StatsOut:
    now = datetime.now(timezone.utc)
    all_tickets = db.query(Ticket).all()
    open_tickets = [t for t in all_tickets if t.status in ("queued", "in_progress")]

    total_tickets = len(all_tickets)

    # Route and status counts
    counts_by_route: dict[str, int] = {}
    counts_by_status: dict[str, int] = {}
    for t in all_tickets:
        counts_by_route[t.route] = counts_by_route.get(t.route, 0) + 1
        counts_by_status[t.status] = counts_by_status.get(t.status, 0) + 1

    # Wait times for open tickets
    wait_times = [
        max((now - ensure_utc(t.created_at)).total_seconds() / 60.0, 0.0)
        for t in open_tickets
    ]

    avg_wait = float(np.mean(wait_times)) if wait_times else 0.0
    p95_wait = float(np.percentile(wait_times, 95)) if wait_times else 0.0

    # Wait times by segment
    cust_map = {c.id: c.segment for c in db.query(Customer).all()}
    seg_waits: dict[str, list[float]] = {}
    for t in open_tickets:
        seg = cust_map.get(t.customer_id, "unknown") if t.customer_id else "unknown"
        w = max((now - ensure_utc(t.created_at)).total_seconds() / 60.0, 0.0)
        seg_waits.setdefault(seg, []).append(w)

    avg_wait_by_segment = {
        seg: round(float(np.mean(ws)), 1)
        for seg, ws in seg_waits.items()
    }

    # Overrides and suggestion acceptance from Feedback
    feedbacks = db.query(Feedback).all()
    override_count = sum(1 for f in feedbacks if f.kind == "override")
    helpful_count = sum(1 for f in feedbacks if f.helpful is True)
    unhelpful_count = sum(1 for f in feedbacks if f.helpful is False)

    total_rated_kb = helpful_count + unhelpful_count
    suggestion_acc = (helpful_count / total_rated_kb) if total_rated_kb > 0 else 0.0
    override_rate = (override_count / total_tickets) if total_tickets > 0 else 0.0

    # Abstention rate
    none_count = sum(1 for t in all_tickets if t.kb_action == "none")
    abstention_rate = (none_count / total_tickets) if total_tickets > 0 else 0.0

    return StatsOut(
        total_tickets=total_tickets,
        counts_by_route=counts_by_route,
        counts_by_status=counts_by_status,
        avg_wait_minutes=round(avg_wait, 1),
        p95_wait_minutes=round(p95_wait, 1),
        avg_wait_by_segment=avg_wait_by_segment,
        override_rate=round(override_rate, 3),
        suggestion_acceptance_rate=round(suggestion_acc, 3),
        abstention_rate=round(abstention_rate, 3),
    )


@router.get("/config")
def get_config() -> dict:
    return {
        "nlp_mode": settings.nlp_mode,
        "weights": WEIGHTS,
        "senior_score": settings.senior_score,
        "tier2_score": settings.tier2_score,
        "frustration_senior": settings.frustration_senior,
        "kb_suggest_threshold": settings.kb_suggest_threshold,
        "kb_auto_threshold": settings.kb_auto_threshold,
        "rescore_interval_sec": settings.rescore_interval_sec,
    }


@lru_cache(maxsize=1)
def _simulation() -> dict:
    from eval.simulate import AGENTS, N, SEED, SLA, run_simulation
    return {
        "setup": {"seed": SEED, "agents": AGENTS, "tickets": N, "sla_min": SLA, "window_min": 480},
        "results": run_simulation(),
    }


@router.get("/simulation")
def get_simulation() -> dict:
    return _simulation()


@router.post("/admin/rescore")
def force_rescore(db: Session = Depends(get_db)) -> dict[str, str | int]:
    count = rescore_open(db)
    return {
        "status": "ok",
        "message": f"Successfully rescored {count} open tickets",
        "rescored_count": count,
    }
