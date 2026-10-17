from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any
from sqlalchemy.orm import Session

from app.categories import CATEGORY_BY_ID, level_name
from app.config import (
    DEFAULT_SLA_MIN,
    RENEWAL_RISK_DAYS,
    RENEWAL_RISK_POINTS,
    REPEAT_CONTACT_MIN,
    REPEAT_CONTACT_POINTS,
    settings,
)
from app.models import CallbackRequest, Customer, KbArticle, Message, Ticket, User
from app.nlp.analyzer import analyse
from app.nlp.kb import get_kb
from app.schemas import (
    AgentSummary,
    AnalysisOut,
    CustomerSummary,
    CustomerTicketOut,
    KbOut,
    MessageOut,
    TicketIn,
    TicketOut,
)
from app.services.priority import PriorityResult, compute_priority
from app.services.router import LEVEL, NEXT_LEVEL, Decision, decide, higher
from app.services.value import customer_value

log = logging.getLogger("triage.service")

OPEN = ("queued", "in_progress")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


def pick_agent(db: Session, level: str) -> int | None:
    """Least-loaded active agent at the level (playbook 10.3); None if nobody holds that role yet."""
    pool = db.query(User).filter(User.role == level, User.active.is_(True)).all()
    if not pool:
        return None
    return min(pool, key=lambda a: (open_load(db, a.id), a.id)).id


def _explanation(t: Ticket) -> dict:
    try:
        return json.loads(t.explanation_json or "{}")
    except ValueError:
        return {}


def score_ticket(t: Ticket, now: datetime) -> PriorityResult:
    expl = _explanation(t)
    return compute_priority(t.urgency, t.frustration, t.value, wait_minutes(t.created_at, now),
                            t.sla_minutes or DEFAULT_SLA_MIN, expl.get("static_boosts", {}))


def store_priority(t: Ticket, pr: PriorityResult) -> None:
    expl = _explanation(t)
    expl.update(components=pr.components, contributions=pr.contributions, boosts=pr.boosts, reasons=pr.reasons)
    t.explanation_json = json.dumps(expl)


def add_system_message(db: Session, t: Ticket, text: str) -> None:
    db.add(Message(ticket_id=t.id, author_role="system", kind="system", body=text))


def route_ticket(db: Session, t: Ticket, d: Decision, note: bool = True) -> str:
    """Apply a routing decision. Returns the previous route."""
    old = t.route
    t.route, t.route_reason = d.route, d.reason
    t.updated_at = utcnow()
    if d.route in LEVEL:
        if d.route != old or t.assigned_agent_id is None:
            t.assigned_agent_id = pick_agent(db, d.route)
            if d.route != old and t.status == "in_progress":
                t.status = "queued"   # the new level has to pick it up
    else:
        t.assigned_agent_id = None
    if note and t.id and d.route != old and old in LEVEL:
        add_system_message(db, t, f"Moved to {level_name(d.route)}: {d.reason}")
    return old


def flags_of(t: Ticket) -> list[str]:
    return [f for f in t.critical_flags.split(",") if f]


# ---------------------------------------------------------------- pipeline
def process_ticket(
    db: Session,
    payload: TicketIn,
    customer: Customer | None,
    created_by: User | None = None,
    created_at: datetime | None = None,
) -> Ticket:
    now = utcnow()
    created = ensure_utc(created_at) if created_at else now
    text = f"{payload.subject}. {payload.body}" if payload.subject else payload.body
    category = payload.category if payload.category in CATEGORY_BY_ID else "howto"

    analysis = analyse(text)

    kb = active_kb(db)
    kb_match = kb.match(text) if kb else None
    kb_conf = kb_match.confidence if kb_match else 0.0

    value, value_parts, sla, prior_7d = customer_context(db, customer, created)
    boosts = static_boosts(customer, prior_7d, analysis.frustration, analysis.signals.get("neg", 0.0))

    # Priority as of arrival (back-dated seed tickets are aged afterwards by the re-scorer).
    pr = compute_priority(analysis.urgency, analysis.frustration, value, 0.0, sla, boosts)
    d = decide(pr.route_score, analysis.frustration, analysis.intent, analysis.critical_flags, kb_conf,
               value=value, confidence=analysis.confidence, kb_thresholds=kb_thresholds_for(kb),
               mode=analysis.mode, category=category)

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
        created_by_id=created_by.id if created_by else None,
        category=category,
        subject=payload.subject,
        body=payload.body,
        channel=payload.channel,
        created_at=created,
        updated_at=created,
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
    route_ticket(db, ticket, d, note=False)
    db.add(ticket)
    db.flush()
    if d.route == "auto_kb":
        add_system_message(db, ticket, "Answered automatically from the knowledge base.")
    else:
        add_system_message(db, ticket, f"Routed to {level_name(d.route)}: {d.reason}")
    db.commit()
    db.refresh(ticket)
    return ticket


def rescore_and_route(db: Session, t: Ticket, reason_prefix: str, now: datetime | None = None,
                      floor: str | None = None) -> str:
    """Re-score and escalate if needed (never moves down). Returns the previous route."""
    now = now or utcnow()
    pr = score_ticket(t, now)
    if not t.priority_locked:
        t.priority = max(t.priority, pr.score)
    store_priority(t, pr)
    old = t.route
    if t.route_locked and t.route in LEVEL:
        return old
    d = decide(pr.route_score, t.frustration, t.intent, flags_of(t), 0.0, value=t.value, allow_auto=False,
               mode=t.analysis_mode, category=t.category)
    target = higher(d.route, t.route) if t.route in LEVEL else d.route
    if floor:
        target = higher(target, floor)
    if target != t.route:
        reason = d.reason if target == d.route else t.route_reason
        route_ticket(db, t, Decision(target, f"{reason_prefix} · {reason}", "none"))
    return old


def escalate_after_kb(db: Session, t: Ticket) -> str:
    """Customer said the KB answer did not help: re-score with higher frustration, send to a human."""
    t.frustration = round(min(1.0, t.frustration + 0.2), 3)
    t.status = "queued"
    t.kb_action = "none"
    t.route = "level1"  # leaves auto-answer; may escalate further below
    t.assigned_agent_id = pick_agent(db, "level1")
    t.route_reason = "Escalated: KB answer did not help"
    add_system_message(db, t, "Customer said the automatic answer did not help.")
    rescore_and_route(db, t, "Escalated: KB answer did not help")
    return "auto_kb"


def escalate_manually(db: Session, t: Ticket, actor: User, reason: str) -> str:
    target = NEXT_LEVEL.get(t.route)
    if not target:
        raise ValueError("Already at the highest level")
    return route_ticket(db, t, Decision(target, f"Escalated by {actor.name}: {reason}", t.kb_action))


def customer_reply(db: Session, t: Ticket, user: User, body: str) -> tuple[Message, str]:
    """Score the customer's reply; rising frustration or new critical issues escalate live."""
    a = analyse(body)
    msg = Message(ticket_id=t.id, author_id=user.id, author_role="customer", body=body, frustration=a.frustration)
    db.add(msg)
    t.updated_at = utcnow()
    if t.status in ("resolved", "kb_handled"):
        if t.status == "kb_handled":
            t.route, t.kb_action = "level1", "none"
        t.status = "queued"
        t.resolved_at = None
        add_system_message(db, t, "Reopened by the customer's reply.")
    new_flags = [f for f in a.critical_flags if f not in flags_of(t)]
    if new_flags:
        t.critical_flags = ",".join(flags_of(t) + new_flags)
        t.urgency = max(t.urgency, a.urgency)
    rising = a.frustration > t.frustration
    t.frustration = round(max(t.frustration, a.frustration), 3)
    prefix = "Customer reply: " + ("new critical issue" if new_flags else "frustration rising" if rising else "follow-up")
    old = rescore_and_route(db, t, prefix)
    if t.assigned_agent_id is None and t.route in LEVEL:
        t.assigned_agent_id = pick_agent(db, t.route)
    return msg, old


def agent_reply(db: Session, t: Ticket, user: User, body: str) -> Message:
    msg = Message(ticket_id=t.id, author_id=user.id, author_role=user.role, body=body)
    db.add(msg)
    t.updated_at = utcnow()
    if t.status == "queued" and user.role in LEVEL:
        t.status = "in_progress"
        t.assigned_agent_id = user.id
    return msg


# ---------------------------------------------------------------- output
def _kb_out(db: Session, t: Ticket) -> tuple[KbOut, str | None]:
    show_kb = t.kb_action in ("suggest", "auto_reply") or t.route == "auto_kb"
    art = db.get(KbArticle, t.kb_article_id) if t.kb_article_id else None
    kb = KbOut(
        action=t.kb_action,
        article_id=t.kb_article_id if show_kb else None,
        title=art.title if (art and show_kb) else None,
        source=art.source if (art and show_kb) else None,
        answer=art.answer if (art and show_kb) else None,
        confidence=t.kb_confidence,
        rated=t.kb_rated,
    )
    auto_reply = f"{art.answer}\n\nDid this help resolve your question?" if (t.route == "auto_kb" and art) else None
    return kb, auto_reply


def serialise(ticket: Ticket, db: Session) -> TicketOut:
    """Full view for agents and admins."""
    now = utcnow()
    created_utc = ensure_utc(ticket.created_at)
    end = ensure_utc(ticket.resolved_at) if (ticket.status == "resolved" and ticket.resolved_at) else now
    customer_obj = None
    if ticket.customer_id and (cust := db.get(Customer, ticket.customer_id)):
        customer_obj = CustomerSummary(id=cust.id, name=cust.name, segment=cust.segment, plan=cust.plan)
    agent_obj = None
    if ticket.assigned_agent_id and (a := db.get(User, ticket.assigned_agent_id)):
        agent_obj = AgentSummary(id=a.id, name=a.name, level=a.role)
    expl = _explanation(ticket)
    kb, auto_reply = _kb_out(db, ticket)
    cat = CATEGORY_BY_ID.get(ticket.category, {"label": ticket.category})
    return TicketOut(
        id=ticket.id,
        subject=ticket.subject,
        body=ticket.body,
        category=ticket.category,
        category_label=cat["label"],
        channel=ticket.channel,
        status=ticket.status,
        created_at=created_utc,
        updated_at=ensure_utc(ticket.updated_at or ticket.created_at),
        wait_minutes=round(wait_minutes(created_utc, end), 1),
        sla_minutes=ticket.sla_minutes,
        customer=customer_obj,
        analysis=AnalysisOut(
            frustration=ticket.frustration,
            urgency=ticket.urgency,
            intent=ticket.intent,
            critical_flags=flags_of(ticket),
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
        level_name=level_name(ticket.route),
        route_locked=ticket.route_locked,
        route_reason=ticket.route_reason,
        manager_flag=ticket.manager_flag,
        reasons=expl.get("reasons", []),
        kb=kb,
        auto_reply=auto_reply,
        assigned_agent=agent_obj,
        message_count=db.query(Message).filter(Message.ticket_id == ticket.id, Message.kind == "message").count(),
        open_callbacks=db.query(CallbackRequest).filter(CallbackRequest.ticket_id == ticket.id,
                                                        CallbackRequest.status != "done").count(),
    )


def serialise_for_customer(ticket: Ticket, db: Session) -> CustomerTicketOut:
    agent_name = None
    if ticket.assigned_agent_id and (a := db.get(User, ticket.assigned_agent_id)):
        agent_name = a.name.split()[0]
    kb, auto_reply = _kb_out(db, ticket)
    if ticket.route != "auto_kb":
        kb = KbOut(action="none", rated=ticket.kb_rated)
    cat = CATEGORY_BY_ID.get(ticket.category, {"label": ticket.category})
    return CustomerTicketOut(
        id=ticket.id,
        subject=ticket.subject,
        body=ticket.body,
        category=ticket.category,
        category_label=cat["label"],
        status=ticket.status,
        route=ticket.route,
        level_name=level_name(ticket.route),
        created_at=ensure_utc(ticket.created_at),
        updated_at=ensure_utc(ticket.updated_at or ticket.created_at),
        agent_name=agent_name,
        auto_reply=auto_reply,
        kb=kb,
        live_chat=ticket.route == "level3",
    )


def serialise_message(m: Message, db: Session, viewer: User) -> MessageOut:
    if m.kind == "system" or m.author_id is None:
        name = "System"
    elif (u := db.get(User, m.author_id)):
        name = u.name if (viewer.role != "customer" or u.role == "customer") else u.name.split()[0]
    else:
        name = "Unknown"
    return MessageOut(
        id=m.id,
        author_name=name,
        author_role=m.author_role,
        kind=m.kind,
        body=m.body,
        created_at=ensure_utc(m.created_at),
        frustration=m.frustration if viewer.role != "customer" else None,
        mine=m.author_id == viewer.id,
    )
