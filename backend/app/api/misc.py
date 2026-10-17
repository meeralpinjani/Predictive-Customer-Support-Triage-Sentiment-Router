from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import DEFAULT_SLA_MIN, REPEAT_CONTACT_POINTS, RENEWAL_RISK_POINTS, SLA_RISK_POINTS, SLA_RISK_START, WEIGHTS, settings
from app.db import get_db
from app.models import Customer, Feedback, KbArticle, Ticket
from app.nlp import frustration_model
from app.schemas import CustomerOut, HealthOut, KbTestIn, StatsOut, WhatIfIn
from app.services.priority import compute_priority
from app.services.rescore import rescore_open
from app.services.router import decide, frustration_threshold
from app.services.triage import OPEN, active_kb, kb_thresholds_for, wait_minutes, _explanation

router = APIRouter(prefix="/api", tags=["system"])

REPORT_PATH = Path(__file__).resolve().parents[2] / "eval" / "report.json"


def _models_status() -> str:
    if settings.nlp_mode != "hf":
        return "off"
    from app.nlp import hf
    return hf.status()


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
    models = _models_status()
    kb = active_kb(db) if db_status == "ok" else None
    return HealthOut(
        status="ok" if db_status == "ok" else "degraded",
        nlp_mode="hf" if models == "ready" else "rules",
        nlp_requested=settings.nlp_mode,
        models=models,
        kb_size=kb_count,
        kb_kind=getattr(kb, "kind", "none"),
        db=db_status,
    )


@router.get("/customers", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db)) -> list[Customer]:
    return db.query(Customer).order_by(Customer.id).all()


@router.get("/kb-articles")
def list_kb_articles(db: Session = Depends(get_db)) -> list[dict]:
    out = []
    for a in db.query(KbArticle).all():
        try:
            qs = json.loads(a.questions)
        except ValueError:
            qs = [a.questions]
        out.append({"id": a.id, "title": a.title, "questions": qs, "answer": a.answer, "source": a.source})
    return out


@router.post("/kb/test-match")
def test_kb_match(payload: KbTestIn, db: Session = Depends(get_db)) -> dict:
    kb = active_kb(db)
    suggest_th, auto_th = kb_thresholds_for(kb)
    match = kb.match(payload.text) if kb else None
    base = {"suggest_threshold": suggest_th, "auto_threshold": auto_th, "matcher": getattr(kb, "kind", "none")}
    if not match:
        return {"matched": False, "confidence": 0.0, "action": "none", **base}
    action = "auto_reply" if match.confidence >= auto_th else "suggest" if match.confidence >= suggest_th else "none"
    return {
        "matched": True,
        "article_id": match.article_id,
        "title": match.title,
        "source": match.source,
        "answer": match.answer,
        "confidence": match.confidence,
        "action": action,
        **base,
    }


@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)) -> StatsOut:
    now = datetime.now(timezone.utc)
    all_tickets = db.query(Ticket).all()
    open_tickets = [t for t in all_tickets if t.status in OPEN]
    total = len(all_tickets)

    counts_by_route: dict[str, int] = {}
    counts_by_status: dict[str, int] = {}
    for t in all_tickets:
        counts_by_route[t.route] = counts_by_route.get(t.route, 0) + 1
        counts_by_status[t.status] = counts_by_status.get(t.status, 0) + 1

    waits = [wait_minutes(t.created_at, now) for t in open_tickets]
    seg = {c.id: c.segment for c in db.query(Customer).all()}
    seg_waits: dict[str, list[float]] = {}
    for t, w in zip(open_tickets, waits):
        seg_waits.setdefault(seg.get(t.customer_id, "unknown"), []).append(w)

    feedback = db.query(Feedback).all()
    overridden = {f.ticket_id for f in feedback if f.kind == "override"}
    helpful = sum(1 for f in feedback if f.helpful is True)
    unhelpful = sum(1 for f in feedback if f.helpful is False)
    human_routed = sum(1 for t in all_tickets if t.route != "auto_kb")

    return StatsOut(
        total_tickets=total,
        open_tickets=len(open_tickets),
        counts_by_route=counts_by_route,
        counts_by_status=counts_by_status,
        avg_wait_minutes=round(float(np.mean(waits)), 1) if waits else 0.0,
        p95_wait_minutes=round(float(np.percentile(waits, 95)), 1) if waits else 0.0,
        avg_wait_by_segment={s: round(float(np.mean(ws)), 1) for s, ws in seg_waits.items()},
        sla_breached_open=sum(1 for t, w in zip(open_tickets, waits) if w > (t.sla_minutes or DEFAULT_SLA_MIN)),
        deflection_rate=round(counts_by_route.get("auto_kb", 0) / total, 3) if total else 0.0,
        override_rate=round(len(overridden) / human_routed, 3) if human_routed else 0.0,
        suggestion_acceptance_rate=round(helpful / (helpful + unhelpful), 3) if helpful + unhelpful else 0.0,
        abstention_rate=round(sum(1 for t in all_tickets if t.kb_action == "none") / total, 3) if total else 0.0,
        kb_ratings=helpful + unhelpful,
    )


@router.get("/config")
def get_config() -> dict:
    suggest_th, auto_th = settings.kb_thresholds()
    return {
        "nlp_mode": settings.nlp_mode,
        "weights": WEIGHTS,
        "senior_score": settings.senior_score,
        "tier2_score": settings.tier2_score,
        "frustration_senior": frustration_threshold(),
        "vip_value": settings.vip_value,
        "vip_score": settings.vip_score,
        "kb_suggest_threshold": suggest_th,
        "kb_auto_threshold": auto_th,
        "min_auto_confidence": settings.min_auto_confidence,
        "boosts": {
            "repeat_contact": REPEAT_CONTACT_POINTS,
            "renewal_risk": RENEWAL_RISK_POINTS,
            "sla_risk_max": SLA_RISK_POINTS,
            "sla_risk_start": SLA_RISK_START,
        },
        "frustration_model": frustration_model.describe("hf" if settings.nlp_mode == "hf" else "rules"),
        "rescore_interval_sec": settings.rescore_interval_sec,
    }


def _report() -> dict:
    try:
        return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No evaluation report yet. Run: python -m eval.run_all")


@router.get("/eval")
def get_eval() -> dict:
    """Offline evaluation results (eval/report.json), so the demo never computes them live."""
    return _report()


@router.get("/simulation")
def get_simulation() -> dict:
    return _report()["simulation"]


@router.post("/whatif")
def what_if(payload: WhatIfIn, db: Session = Depends(get_db)) -> dict:
    """Preview how the open queue would re-rank under other weights/thresholds. Saves nothing."""
    weights = dict(WEIGHTS)
    if payload.weights:
        weights.update(payload.weights)
        total = sum(weights.values()) or 1.0
        weights = {k: v / total for k, v in weights.items()}

    now = datetime.now(timezone.utc)
    open_tickets = db.query(Ticket).filter(Ticket.status.in_(OPEN)).all()
    current = sorted(open_tickets, key=lambda t: (-t.priority, t.created_at))
    current_pos = {t.id: i + 1 for i, t in enumerate(current)}

    rows = []
    for t in open_tickets:
        pr = compute_priority(t.urgency, t.frustration, t.value, wait_minutes(t.created_at, now),
                              t.sla_minutes or DEFAULT_SLA_MIN, _explanation(t).get("static_boosts", {}), weights)
        flags = [f for f in t.critical_flags.split(",") if f]
        d = decide(pr.route_score, t.frustration, t.intent, flags, t.kb_confidence, value=t.value,
                   allow_auto=False, senior_score=payload.senior_score, tier2_score=payload.tier2_score,
                   frustration_senior=payload.frustration_senior, mode=t.analysis_mode)
        route = t.route if t.route_locked else d.route
        rows.append({"id": t.id, "score": t.priority if t.priority_locked else pr.score, "route": route,
                     "old_score": t.priority, "old_route": t.route, "created_at": t.created_at})

    rows.sort(key=lambda r: (-r["score"], r["created_at"]))
    for i, r in enumerate(rows):
        r["position"] = i + 1
        r["old_position"] = current_pos[r["id"]]
        r.pop("created_at")
    return {
        "weights": {k: round(v, 3) for k, v in weights.items()},
        "tickets": rows,
        "route_changes": sum(1 for r in rows if r["route"] != r["old_route"]),
        "moved": sum(1 for r in rows if r["position"] != r["old_position"]),
    }


@router.post("/admin/rescore")
def force_rescore(db: Session = Depends(get_db)) -> dict[str, str | int]:
    count = rescore_open(db)
    return {"status": "ok", "message": f"Rescored {count} open tickets", "rescored_count": count}
