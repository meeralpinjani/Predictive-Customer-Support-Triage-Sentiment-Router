from datetime import datetime, timezone
import json
import logging
from typing import Any
from sqlalchemy.orm import Session

from app.config import DEFAULT_SLA_MIN, SEGMENT_VALUE, UNKNOWN_VALUE, settings
from app.models import Agent, Customer, KbArticle, Ticket
from app.nlp.analyzer import analyse
from app.nlp.kb import get_kb
from app.nlp.rules import INTENT_META
from app.schemas import (
    AnalysisOut,
    CustomerSummary,
    KbOut,
    TicketIn,
    TicketOut,
)
from app.services.priority import compute_priority
from app.services.router import LEVEL, decide

log = logging.getLogger("triage.service")


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def enrich(
    db: Session,
    customer_id: str | None,
    created_at: datetime,
    now: datetime | None = None,
) -> tuple[float, int, str, float, str]:
    now = now or datetime.now(timezone.utc)
    created_utc = ensure_utc(created_at)
    wait_min = round(max((now - created_utc).total_seconds() / 60.0, 0.0), 1)

    if not customer_id:
        return UNKNOWN_VALUE, DEFAULT_SLA_MIN, "unknown", wait_min, "Unknown Customer"

    cust = db.get(Customer, customer_id)
    if not cust:
        return UNKNOWN_VALUE, DEFAULT_SLA_MIN, "unknown", wait_min, "Unknown Customer"

    val = SEGMENT_VALUE.get(cust.segment.lower(), UNKNOWN_VALUE)
    sla = cust.sla_minutes or DEFAULT_SLA_MIN
    return val, sla, cust.segment, wait_min, cust.name


def pick_agent(db: Session, level: str, skill: str) -> int | None:
    pool = db.query(Agent).filter(Agent.level == level).all()
    if not pool:
        return None

    def load(a: Agent) -> int:
        return (
            db.query(Ticket)
            .filter(
                Ticket.assigned_agent_id == a.id,
                Ticket.status.in_(["queued", "in_progress"]),
            )
            .count()
        )

    skilled = [a for a in pool if skill in (a.skills or "")] or pool
    chosen = min(skilled, key=load)
    return chosen.id


def load_kb_if_needed(db: Session) -> None:
    articles = db.query(KbArticle).all()
    art_dicts = [
        {
            "id": a.id,
            "title": a.title,
            "questions": a.questions,
            "answer": a.answer,
            "source": a.source,
        }
        for a in articles
    ]
    get_kb(art_dicts, mode=settings.nlp_mode)


def process_ticket(db: Session, payload: TicketIn) -> Ticket:
    now = datetime.now(timezone.utc)
    text = f"{payload.subject}. {payload.body}" if payload.subject else payload.body

    # 1. NLP Analysis
    analysis = analyse(text)

    # 2. KB Matching
    kb_inst = get_kb(mode=settings.nlp_mode)
    if kb_inst is None:
        load_kb_if_needed(db)
        kb_inst = get_kb(mode=settings.nlp_mode)

    kb_match = kb_inst.match(text) if kb_inst else None
    kb_conf = kb_match.confidence if kb_match else 0.0
    kb_article_id = kb_match.article_id if kb_match else None

    # 3. Context Enrichment
    val, sla, segment, wait_min, cust_name = enrich(db, payload.customer_id, now, now)

    # 4. Priority Calculation
    pr = compute_priority(analysis.urgency, analysis.frustration, val, wait_min, sla)

    # 5. Routing Decision
    d = decide(pr.score, analysis.frustration, analysis.intent, analysis.critical_flags, kb_conf)

    # 6. Status and Agent Assignment
    status = "kb_handled" if d.route == "auto_kb" else "queued"
    assigned_agent_id = None
    if d.route in LEVEL:
        skill = INTENT_META.get(analysis.intent, {}).get("skill", "general")
        assigned_agent_id = pick_agent(db, d.route, skill)

    explanation = {
        "components": pr.components,
        "contributions": pr.contributions,
        "rules_fired": analysis.critical_flags,
        "route_reason": d.reason,
        "mode": analysis.mode,
        "reasons": pr.reasons,
    }

    ticket = Ticket(
        customer_id=payload.customer_id,
        subject=payload.subject,
        body=payload.body,
        channel=payload.channel,
        created_at=now,
        status=status,
        frustration=analysis.frustration,
        urgency=analysis.urgency,
        value=val,
        intent=analysis.intent,
        critical_flags=",".join(analysis.critical_flags),
        priority=pr.score,
        route=d.route,
        route_reason=d.reason,
        route_locked=False,
        explanation_json=json.dumps(explanation),
        kb_article_id=kb_article_id,
        kb_confidence=kb_conf,
        kb_action=d.kb_action,
        analysis_mode=analysis.mode,
        assigned_agent_id=assigned_agent_id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def serialise(ticket: Ticket, db: Session) -> TicketOut:
    now = datetime.now(timezone.utc)
    created_utc = ensure_utc(ticket.created_at)
    wait_min = round(max((now - created_utc).total_seconds() / 60.0, 0.0), 1)

    customer_obj = None
    if ticket.customer_id:
        cust = db.get(Customer, ticket.customer_id)
        if cust:
            customer_obj = CustomerSummary(id=cust.id, name=cust.name, segment=cust.segment)

    try:
        expl = json.loads(ticket.explanation_json)
    except Exception:
        expl = {}

    components = expl.get("components", {
        "urgency": ticket.urgency,
        "frustration": ticket.frustration,
        "value": ticket.value,
        "age": 0.0,
    })
    contributions = expl.get("contributions", {})
    reasons = expl.get("reasons", [])

    kb_article = db.get(KbArticle, ticket.kb_article_id) if ticket.kb_article_id else None
    kb_out = KbOut(
        action=ticket.kb_action,
        article_id=ticket.kb_article_id if ticket.kb_action in ("suggest", "auto_reply") else None,
        title=kb_article.title if (kb_article and ticket.kb_action in ("suggest", "auto_reply")) else None,
        source=kb_article.source if (kb_article and ticket.kb_action in ("suggest", "auto_reply")) else None,
        confidence=ticket.kb_confidence,
    )

    auto_reply = None
    if ticket.route == "auto_kb" and kb_article:
        auto_reply = f"{kb_article.answer}\n\nDid this help resolve your question?"

    flags = [f for f in ticket.critical_flags.split(",") if f]

    return TicketOut(
        id=ticket.id,
        subject=ticket.subject,
        body=ticket.body,
        channel=ticket.channel,
        status=ticket.status,
        created_at=created_utc,
        wait_minutes=wait_min,
        customer=customer_obj,
        analysis=AnalysisOut(
            frustration=ticket.frustration,
            urgency=ticket.urgency,
            intent=ticket.intent,
            critical_flags=flags,
            mode=ticket.analysis_mode,
        ),
        priority=ticket.priority,
        components=components,
        contributions=contributions,
        route=ticket.route,
        route_locked=ticket.route_locked,
        route_reason=ticket.route_reason,
        reasons=reasons,
        kb=kb_out,
        auto_reply=auto_reply,
        assigned_agent_id=ticket.assigned_agent_id,
    )
