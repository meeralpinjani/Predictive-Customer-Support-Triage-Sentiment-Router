from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any
from sqlalchemy.orm import Session

from app.config import (
    DEFAULT_SLA_MIN,
    RENEWAL_RISK_DAYS,
    RENEWAL_RISK_POINTS,
    REPEAT_CONTACT_MIN,
    REPEAT_CONTACT_POINTS,
    settings,
)
from app.models import Agent, Customer, KbArticle, Ticket
from app.nlp.analyzer import analyse
from app.nlp.kb import get_kb
from app.nlp.rules import INTENT_META
from app.schemas import (
    AgentSummary,
    AnalysisOut,
    CustomerSummary,
    KbOut,
    TicketIn,
    TicketOut,
)
from app.services.priority import PriorityResult, compute_priority
from app.services.router import LEVEL, Decision, decide
from app.services.value import customer_value

log = logging.getLogger("triage.service")

OPEN = ("queued", "in_progress")


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def wait_minutes(created_at: datetime, now: datetime) -> float:
    return max((now - ensure_utc(created_at)).total_seconds() / 60.0, 0.0)


# ---------------------------------------------------------------- knowledge base
def load_kb(db: Session) -> Any:
    articles = [
        {"id": a.id, "title": a.title, "questions": a.questions, "answer": a.answer, "source": a.source}
        for a in db.query(KbArticle).all()
    ]
    mode = settings.nlp_mode
    if mode == "hf":
        from app.nlp import hf
        if not hf.ready():
            mode = "rules"
    return get_kb(articles, mode=mode)


def active_kb(db: Session) -> Any:
    """Current KB index; upgrades TF-IDF to MiniLM once the HF models finish loading."""
    kb = get_kb()
    if kb is None:
        return load_kb(db)
    if settings.nlp_mode == "hf" and getattr(kb, "kind", "") != "minilm":
        from app.nlp import hf
        if hf.ready():
            return load_kb(db)
    return kb


def kb_thresholds_for(kb: Any) -> tuple[float, float]:
    return settings.kb_thresholds("hf" if getattr(kb, "kind", "") == "minilm" else "rules")


# ---------------------------------------------------------------- helpers
def customer_context(db: Session, customer: Customer | None, now: datetime) -> tuple[float, dict, int, int]:
    """Returns (value, value parts, sla minutes, tickets in last 7 days)."""
    if customer is None:
        v = customer_value(None)
        return v.value, v.parts, DEFAULT_SLA_MIN, 0
    since_30 = now - timedelta(days=30)
    since_7 = now - timedelta(days=7)
    recent = db.query(Ticket).filter(Ticket.customer_id == customer.id, Ticket.created_at >= since_30).all()
    recent_7 = sum(1 for t in recent if ensure_utc(t.created_at) >= since_7)
    v = customer_value(customer.segment, customer.ltv, customer.churn_risk, customer.renewal_days, len(recent))
    return v.value, v.parts, customer.sla_minutes or DEFAULT_SLA_MIN, recent_7


def static_boosts(customer: Customer | None, prior_contacts_7d: int, frustration: float, neg: float) -> dict[str, float]:
    boosts: dict[str, float] = {}
    if customer is None:
        return boosts
    if prior_contacts_7d + 1 >= REPEAT_CONTACT_MIN:
        boosts["repeat_contact"] = REPEAT_CONTACT_POINTS
    if (
        customer.renewal_days is not None
        and customer.renewal_days < RENEWAL_RISK_DAYS
        and (frustration >= 0.4 or neg >= 0.5)
    ):
        boosts["renewal_risk"] = RENEWAL_RISK_POINTS
    return boosts


def open_load(db: Session, agent_id: int) -> int:
    return db.query(Ticket).filter(Ticket.assigned_agent_id == agent_id, Ticket.status.in_(OPEN)).count()


def pick_agent(db: Session, level: str, skill: str) -> int | None:
    """Least-loaded agent at the level, preferring one with the matching skill (playbook 10.3)."""
    pool = db.query(Agent).filter(Agent.level == level).all()
    if not pool:
        return None
    skilled = [a for a in pool if skill in (a.skills or "").split(",")] or pool
    return min(skilled, key=lambda a: (open_load(db, a.id), a.id)).id


def score_ticket(t: Ticket, now: datetime) -> PriorityResult:
    expl = _explanation(t)
    return compute_priority(t.urgency, t.frustration, t.value, wait_minutes(t.created_at, now),
                            t.sla_minutes or DEFAULT_SLA_MIN, expl.get("static_boosts", {}))


def _explanation(t: Ticket) -> dict:
    try:
        return json.loads(t.explanation_json or "{}")
    except ValueError:
        return {}


def store_priority(t: Ticket, pr: PriorityResult) -> None:
    expl = _explanation(t)
    expl.update(components=pr.components, contributions=pr.contributions, boosts=pr.boosts, reasons=pr.reasons)
    t.explanation_json = json.dumps(expl)


def route_ticket(db: Session, t: Ticket, d: Decision) -> None:
    old = t.route
    t.route, t.route_reason = d.route, d.reason
    if d.route in LEVEL and (d.route != old or t.assigned_agent_id is None):
        t.assigned_agent_id = pick_agent(db, d.route, INTENT_META.get(t.intent, {}).get("skill", "general"))
    elif d.route not in LEVEL:
        t.assigned_agent_id = None


# ---------------------------------------------------------------- pipeline
def process_ticket(db: Session, payload: TicketIn, created_at: datetime | None = None) -> Ticket:
    now = datetime.now(timezone.utc)
    created = ensure_utc(created_at) if created_at else now
    text = f"{payload.subject}. {payload.body}" if payload.subject else payload.body

    # 1. NLP analysis
    analysis = analyse(text)

    # 2. Knowledge base
    kb = active_kb(db)
    kb_match = kb.match(text) if kb else None
    kb_conf = kb_match.confidence if kb_match else 0.0
    thresholds = kb_thresholds_for(kb)

    # 3. Customer context
    customer = db.get(Customer, payload.customer_id) if payload.customer_id else None
    value, value_parts, sla, prior_7d = customer_context(db, customer, created)
    boosts = static_boosts(customer, prior_7d, analysis.frustration, analysis.signals.get("neg", 0.0))

    # 4. Priority, as of arrival (back-dated tickets are aged afterwards by the re-scorer)
    pr = compute_priority(analysis.urgency, analysis.frustration, value, 0.0, sla, boosts)

    # 5. Routing
    d = decide(pr.route_score, analysis.frustration, analysis.intent, analysis.critical_flags, kb_conf,
               value=value, confidence=analysis.confidence, kb_thresholds=thresholds, mode=analysis.mode)

    explanation = {
        "components": pr.components,
        "contributions": pr.contributions,
        "boosts": pr.boosts,
        "static_boosts": boosts,
        "reasons": pr.reasons,
        "value_parts": value_parts,
        "signals": analysis.signals,
        "rules_fired": analysis.critical_flags,
        "mode": analysis.mode,
        "kb_kind": getattr(kb, "kind", "none"),
    }

    ticket = Ticket(
        customer_id=customer.id if customer else None,
        subject=payload.subject,
        body=payload.body,
        channel=payload.channel,
        created_at=created,
        status="kb_handled" if d.route == "auto_kb" else "queued",
        frustration=analysis.frustration,
        urgency=analysis.urgency,
        value=value,
        sla_minutes=sla,
        intent=analysis.intent,
        language=analysis.language,
        critical_flags=",".join(analysis.critical_flags),
        manager_flag=analysis.manager_flag,
        priority=pr.score,
        explanation_json=json.dumps(explanation),
        kb_article_id=kb_match.article_id if kb_match else None,
        kb_confidence=kb_conf,
        kb_action=d.kb_action,
        analysis_mode=analysis.mode,
        analysis_confidence=analysis.confidence,
    )
    route_ticket(db, ticket, d)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def escalate_after_kb(db: Session, t: Ticket, now: datetime | None = None) -> None:
    """Customer said the KB answer did not help: re-score with higher frustration, send to a human."""
    now = now or datetime.now(timezone.utc)
    t.frustration = round(min(1.0, t.frustration + 0.2), 3)
    t.status = "queued"
    t.kb_action = "none"
    pr = score_ticket(t, now)
    t.priority = pr.score
    store_priority(t, pr)
    flags = [f for f in t.critical_flags.split(",") if f]
    d = decide(pr.route_score, t.frustration, t.intent, flags, 0.0, value=t.value, allow_auto=False,
               mode=t.analysis_mode)
    route_ticket(db, t, Decision(d.route, f"Escalated: KB answer did not help · {d.reason}", "none"))


# ---------------------------------------------------------------- output
def serialise(ticket: Ticket, db: Session) -> TicketOut:
    now = datetime.now(timezone.utc)
    created_utc = ensure_utc(ticket.created_at)
    wait_min = round(wait_minutes(created_utc, now), 1)
    if ticket.status == "resolved" and ticket.resolved_at:
        wait_min = round(wait_minutes(created_utc, ensure_utc(ticket.resolved_at)), 1)

    customer_obj = None
    if ticket.customer_id:
        cust = db.get(Customer, ticket.customer_id)
        if cust:
            customer_obj = CustomerSummary(id=cust.id, name=cust.name, segment=cust.segment, plan=cust.plan)

    agent_obj = None
    if ticket.assigned_agent_id:
        a = db.get(Agent, ticket.assigned_agent_id)
        if a:
            agent_obj = AgentSummary(id=a.id, name=a.name, level=a.level)

    expl = _explanation(ticket)
    show_kb = ticket.kb_action in ("suggest", "auto_reply")
    kb_article = db.get(KbArticle, ticket.kb_article_id) if ticket.kb_article_id else None
    kb_out = KbOut(
        action=ticket.kb_action,
        article_id=ticket.kb_article_id if show_kb else None,
        title=kb_article.title if (kb_article and show_kb) else None,
        source=kb_article.source if (kb_article and show_kb) else None,
        answer=kb_article.answer if (kb_article and show_kb) else None,
        confidence=ticket.kb_confidence,
        rated=ticket.kb_rated,
    )
    auto_reply = None
    if ticket.route == "auto_kb" and kb_article:
        auto_reply = f"{kb_article.answer}\n\nDid this help resolve your question?"

    return TicketOut(
        id=ticket.id,
        subject=ticket.subject,
        body=ticket.body,
        channel=ticket.channel,
        status=ticket.status,
        created_at=created_utc,
        wait_minutes=wait_min,
        sla_minutes=ticket.sla_minutes,
        customer=customer_obj,
        analysis=AnalysisOut(
            frustration=ticket.frustration,
            urgency=ticket.urgency,
            intent=ticket.intent,
            critical_flags=[f for f in ticket.critical_flags.split(",") if f],
            mode=ticket.analysis_mode,
            confidence=ticket.analysis_confidence,
            language=ticket.language,
            signals=expl.get("signals", {}),
        ),
        priority=ticket.priority,
        priority_locked=ticket.priority_locked,
        components=expl.get("components", {}),
        contributions=expl.get("contributions", {}),
        boosts=expl.get("boosts", {}),
        value_parts=expl.get("value_parts", {}),
        route=ticket.route,
        route_locked=ticket.route_locked,
        route_reason=ticket.route_reason,
        manager_flag=ticket.manager_flag,
        reasons=expl.get("reasons", []),
        kb=kb_out,
        auto_reply=auto_reply,
        assigned_agent=agent_obj,
    )
