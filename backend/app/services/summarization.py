"""Ticket summaries: a readable digest of the conversation. The conversation stays the source of truth.

Primary path (always on, deterministic, milliseconds): an extractive summary built only from saved
ticket fields and saved messages. Every quoted item carries the id of the message it came from
("ticket" = the original description). Nothing is inferred: if a pattern isn't found, the field is
empty. See docs/summaries/DECISIONS.md.

Updates: any meaningful change (new message, status, level or agent change, flags) marks the ticket
"dirty" in the SQLAlchemy session; just before commit a new summary revision is written inside a
savepoint, so a summary problem can never undo or block the change itself. Revisions are
append-only (unique ticket_id + revision): an older job can never overwrite a newer summary.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.categories import level_name
from app.config import settings
from app.models import Customer, Feedback, Message, Ticket, TicketSummary, User

log = logging.getLogger("triage.summary")

CUSTOMER_FIELDS = ("problem_statement", "customer_goal", "conversation_summary", "troubleshooting_attempted",
                   "current_status", "pending_actions", "promises_made", "unresolved_questions")
MAX_CHARS_PER_MESSAGE = 2000
MAX_ITEMS = 6


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- sentence patterns (quote, never infer)
SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")
GOAL = re.compile(r"\b(i (want|need|would like)|we (want|need)|please (help|fix|refund|restore|send|reset|update)|"
                  r"can you|could you|how (do|can) i)\b", re.I)
CLAIM = re.compile(r"\b(i|we) (was|were|have|had|did|paid|bought|tried|got|received|never|already|can't|cannot)\b|"
                   r"\bit (says|shows|keeps|stopped|crashes|crashed)\b|\b(since|for the last) \w+", re.I)
TRIED = re.compile(r"\b(tried|restarted|rebooted|cleared|reinstalled|re-?installed|reset|updated|logged out|"
                   r"switched|disabled|enabled|checked)\b", re.I)
WORKED = re.compile(r"\b(that worked|it works now|working now|works now|fixed it|is fixed|now fixed|resolved it|"
                    r"problem solved|all good now)\b", re.I)
FAILED = re.compile(r"\b(didn'?t work|did not work|still (not|isn'?t|doesn'?t|failing|broken|happening|the same)|"
                    r"no luck|same (error|problem|issue)|still getting)\b", re.I)
AGENT_CONFIRMS = re.compile(r"\b(i can confirm|i'?ve confirmed|we'?ve confirmed|i have confirmed|confirmed that|"
                            r"i'?ve verified|we have verified|we'?ve verified|i can see that)\b", re.I)
PROMISE = re.compile(r"\b(i'?ll|i will|we'?ll|we will)\b", re.I)
ASK_CUSTOMER = re.compile(r"\b(could you|can you|please (send|share|attach|confirm|try|let us know))\b", re.I)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE.findall(text or "") if len(s.strip()) > 3]


def _quote(text: str, ref, role: str | None = None) -> dict:
    item = {"text": text[:300], "source": ref}
    if role:
        item["by"] = role
    return item


def _pick(items: list[dict]) -> list[dict]:
    seen, out = set(), []
    for it in items:
        key = it["text"].lower()
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out[:MAX_ITEMS]


# ---------------------------------------------------------------- source fingerprint
def conversation(db: Session, t: Ticket) -> list[Message]:
    """The last N saved conversation messages (system notes excluded), oldest first."""
    rows = (db.query(Message).filter(Message.ticket_id == t.id, Message.kind == "message")
            .order_by(Message.created_at.desc(), Message.id.desc()).limit(settings.ticket_summary_max_input_messages).all())
    return list(reversed(rows))


def last_message_id(db: Session, ticket_id: int) -> int | None:
    m = (db.query(Message.id).filter(Message.ticket_id == ticket_id)
         .order_by(Message.created_at.desc(), Message.id.desc()).first())
    return m[0] if m else None


def source_key(db: Session, t: Ticket) -> str:
    """What a summary was built from. A different key means the summary is stale."""
    return f"{last_message_id(db, t.id)}|{t.status}|{t.route}|{t.assigned_agent_id}|{t.critical_flags or ''}"


# ---------------------------------------------------------------- extractive summary
def extractive(db: Session, t: Ticket) -> dict:
    msgs = conversation(db, t)
    customer = [("ticket", f"{t.subject or ''}. {t.body or ''}")] + \
               [(m.id, m.body[:MAX_CHARS_PER_MESSAGE]) for m in msgs if m.author_role == "customer"]
    agents = [(m.id, m.body[:MAX_CHARS_PER_MESSAGE]) for m in msgs if m.author_role not in ("customer", "system")]

    first = _sentences(t.body or "")
    problem = ((t.subject + ": ") if t.subject else "") + (" ".join(first[:2]) if first else (t.body or ""))[:300]

    goal = next((_quote(s, ref) for ref, txt in customer for s in _sentences(txt) if GOAL.search(s)), None)
    claims = _pick([_quote(s, ref, "customer") for ref, txt in customer for s in _sentences(txt) if CLAIM.search(s)])
    tried = _pick([_quote(s, ref, role) for role, src in (("customer", customer), ("agent", agents))
                   for ref, txt in src for s in _sentences(txt) if TRIED.search(s)])
    worked = _pick([_quote(s, ref) for ref, txt in customer + agents for s in _sentences(txt) if WORKED.search(s)])
    failed = _pick([_quote(s, ref) for ref, txt in customer + agents for s in _sentences(txt) if FAILED.search(s)])
    promises = _pick([_quote(s, ref, "agent") for ref, txt in agents for s in _sentences(txt) if PROMISE.search(s)])
    asks = [dict(_quote(s, ref), owner="customer") for ref, txt in agents for s in _sentences(txt) if ASK_CUSTOMER.search(s)]
    open_ = t.status in ("queued", "in_progress")
    pending = _pick(([dict(p, owner="agent") for p in promises] + asks) if open_ else [])

    # Customer questions with no support reply after them (message ids grow over time).
    last_agent = max((ref for ref, _ in agents), default=0)
    after_last_reply = [(ref, txt) for ref, txt in customer
                        if (ref == "ticket" and not last_agent) or (ref != "ticket" and ref > last_agent)]
    unanswered = _pick([_quote(s, ref) for ref, txt in after_last_reply for s in _sentences(txt) if s.endswith("?")])         if open_ else []

    cust = db.get(Customer, t.customer_id) if t.customer_id else None
    facts = [{"text": f"Plan on file: {cust.plan}", "source": "customer record"}] if cust and cust.plan else []
    facts.append({"text": f"Category chosen: {t.category}", "source": "ticket record"})
    facts.append({"text": f"Currently with {level_name(t.route)}", "source": "ticket record"} if t.route in ("level1", "level2", "level3")
                 else {"text": "Answered automatically from the help centre", "source": "ticket record"})
    facts += [_quote(s, ref, "agent") for ref, txt in agents for s in _sentences(txt) if AGENT_CONFIRMS.search(s)]

    esc = (db.query(Feedback).filter(Feedback.ticket_id == t.id, Feedback.kind.in_(("escalate", "override")))
           .order_by(Feedback.id.desc()).first())
    moved = (db.query(Message).filter(Message.ticket_id == t.id, Message.kind == "system", Message.body.like("Moved to %"))
             .order_by(Message.id.desc()).first())
    escalation = ({"text": esc.reason, "source": f"{esc.kind} record"} if esc else
                  {"text": moved.body, "source": moved.id} if moved else None)

    n_c = sum(1 for m in msgs if m.author_role == "customer")
    n_a = len(agents)
    last = msgs[-1] if msgs else None
    who = "the customer" if last and last.author_role == "customer" else "support" if last else None
    convo = (f"Ticket opened with {n_c} later customer message(s) and {n_a} support reply(ies)."
             + (f" Last message from {who}." if who else " No replies yet."))

    if t.status in ("resolved", "kb_handled"):
        step = None
    elif unanswered:
        step = "Answer the customer's open question."
    elif n_a == 0:
        step = "Send a first reply."
    elif last and last.author_role == "customer":
        step = "Reply to the customer's latest message."
    elif asks:
        step = "Wait for the customer's reply to the agent's request."
    elif promises:
        step = "Complete the promise made to the customer (see promises)."
    else:
        step = None
    flags = [f for f in (t.critical_flags or "").split(",") if f]
    if flags and t.status not in ("resolved", "kb_handled"):
        step = f"Emergency ({', '.join(flags)}): follow the matching guide first."

    return {
        "problem_statement": problem or None,
        "customer_goal": goal,
        "conversation_summary": convo,
        "customer_claims": claims,
        "confirmed_facts": _pick(facts),
        "troubleshooting_attempted": tried,
        "successful_actions": worked,
        "failed_attempts": failed,
        "current_status": t.status,
        "pending_actions": pending,
        "promises_made": promises,
        "unresolved_questions": unanswered,
        "escalation_reason": escalation,
        "critical_flags": flags,
        "next_recommended_step": {"text": step, "source": "rule"} if step else None,
        "last_included_message_id": last.id if last else None,
    }


# ---------------------------------------------------------------- revisions
def current(db: Session, ticket_id: int) -> TicketSummary | None:
    return (db.query(TicketSummary).filter(TicketSummary.ticket_id == ticket_id)
            .order_by(TicketSummary.revision.desc()).first())


def latest_ready(db: Session, ticket_id: int) -> TicketSummary | None:
    return (db.query(TicketSummary).filter(TicketSummary.ticket_id == ticket_id, TicketSummary.status == "ready")
            .order_by(TicketSummary.revision.desc()).first())


def write_revision(db: Session, t: Ticket, payload: dict | None, status: str, method: str,
                   expected_revision: int | None = None, error: str | None = None,
                   model_name: str | None = None, model_version: str | None = None) -> TicketSummary | None:
    """Insert revision N+1 inside a savepoint. With expected_revision, refuse if the current revision
    moved on (optimistic check). Never raises: returns None if the write lost a race or failed."""
    cur = current(db, t.id)
    rev = (cur.revision if cur else 0)
    if expected_revision is not None and rev != expected_revision:
        return None
    row = TicketSummary(ticket_id=t.id, revision=rev + 1, status=status, method=method, error=error,
                        source_key=source_key(db, t), last_message_id=(payload or {}).get("last_included_message_id"),
                        payload=json.dumps(payload or {}), model_name=model_name, model_version=model_version)
    try:
        with db.begin_nested():
            db.add(row)
        return row
    except IntegrityError:          # a concurrent writer took revision N+1 first
        return None


def refresh(db: Session, t: Ticket) -> TicketSummary | None:
    """Write a fresh extractive revision if the source changed (or none exists)."""
    if not settings.ticket_summary_enabled:
        return None
    cur = current(db, t.id)
    if cur and cur.status == "ready" and cur.source_key == source_key(db, t):
        return cur
    try:
        payload = extractive(db, t)
    except Exception as exc:     # a summary problem must never affect the ticket
        log.warning("Summary failed for ticket %s: %s", t.id, type(exc).__name__)
        db.info.setdefault("after_commit_events", []).append(("summary.failed", t.id))
        return write_revision(db, t, None, "failed", "unavailable", error=type(exc).__name__)
    row = write_revision(db, t, payload, "ready", "extractive")
    if row is not None:
        db.info.setdefault("after_commit_events", []).append(("summary.updated", t.id))
        if settings.ticket_summary_llm_enabled:
            db.info.setdefault("after_commit_llm", []).append((t.id, row.revision))
    return row


def state(db: Session, t: Ticket) -> dict:
    """Freshness for the UI: ready | stale | pending | failed | unavailable (with reason)."""
    cur = current(db, t.id)
    if not settings.ticket_summary_enabled and cur is None:
        return {"status": "unavailable", "reason": "summaries are turned off", "summary": None}
    if cur is None:
        return {"status": "unavailable", "reason": "no summary yet", "summary": None}
    good = cur if cur.status == "ready" else latest_ready(db, t.id)
    if cur.status in ("failed", "pending"):
        status = cur.status
    else:
        status = "ready" if cur.source_key == source_key(db, t) else "stale"
    return {"status": status, "reason": cur.error if cur.status == "failed" else None, "summary": good, "current": cur}


def view(row: TicketSummary | None, customer: bool) -> dict | None:
    if row is None:
        return None
    payload = json.loads(row.payload or "{}")
    if customer:
        payload = {k: v for k, v in payload.items() if k in CUSTOMER_FIELDS}
    return {"revision": row.revision, "method": row.method, "model_name": row.model_name,
            "model_version": row.model_version, "status": row.status, "updated_at": row.updated_at,
            "last_message_id": row.last_message_id, **payload}


# ---------------------------------------------------------------- automatic updates
WATCHED = ("status", "route", "assigned_agent_id", "critical_flags")


def _mark_dirty(session: Session, flush_context) -> None:
    dirty = session.info.setdefault("summary_dirty", set())
    for obj in list(session.new) + list(session.dirty):
        if isinstance(obj, Message) and obj.ticket_id:
            dirty.add(obj.ticket_id)
        elif isinstance(obj, Ticket) and obj.id and obj in session.new:
            dirty.add(obj.id)
        elif isinstance(obj, Ticket) and obj.id and obj in session.dirty:
            st = inspect(obj)
            if any(st.attrs[a].history.has_changes() for a in WATCHED):
                dirty.add(obj.id)


def _before_commit(session: Session) -> None:
    if not settings.ticket_summary_enabled or session.info.get("summary_running"):
        session.info.pop("summary_dirty", None)
        return
    if session.new or session.dirty or session.deleted:
        session.flush()            # pending changes first, so the dirty-ticket list is complete
    ids = session.info.pop("summary_dirty", set())
    if not ids:
        return
    session.info["summary_running"] = True
    try:
        for tid in sorted(ids):
            t = session.get(Ticket, tid)
            if t is not None:
                refresh(session, t)
        session.flush()
        session.info.pop("summary_dirty", None)
    except Exception as exc:
        log.warning("Summary update skipped: %s", type(exc).__name__)
    finally:
        session.info.pop("summary_running", None)


def _after_commit(session: Session) -> None:
    from app import events
    pending = session.info.pop("after_commit_events", [])
    llm = session.info.pop("after_commit_llm", [])
    seen = set()
    for kind, tid in pending:
        if (kind, tid) in seen:
            continue
        seen.add((kind, tid))
        try:
            events.publish(_event(session, kind, tid))
        except Exception:
            pass
    if llm:
        from app.services import summary_llm
        for tid, rev in llm:
            summary_llm.runner.submit((tid, rev))


def _after_rollback(session: Session) -> None:
    for key in ("after_commit_events", "after_commit_llm", "summary_dirty"):
        session.info.pop(key, None)


def _event(session: Session, kind: str, tid: int) -> dict:
    """Ids and states only. Handover events never reach customers (customer_id left empty)."""
    t = session.get(Ticket, tid)
    customer_visible = kind.startswith("summary.")
    return {"type": kind, "ticket_id": tid, "customer_id": t.customer_id if (t and customer_visible) else None,
            "route": t.route if t else None, "old_route": None, "assigned_agent_id": t.assigned_agent_id if t else None,
            "at": utcnow().isoformat()}


def install(session_factory) -> None:
    event.listen(session_factory, "after_flush", _mark_dirty)
    event.listen(session_factory, "before_commit", _before_commit)
    event.listen(session_factory, "after_commit", _after_commit)
    event.listen(session_factory, "after_rollback", _after_rollback)   # real rollbacks only, not savepoints


def reconcile(db: Session) -> int:
    """Periodic check against full history: refresh open tickets whose summary is missing or stale."""
    n = 0
    never = db.query(Ticket).filter(~Ticket.id.in_(db.query(TicketSummary.ticket_id))).all()   # any status
    open_ = db.query(Ticket).filter(Ticket.status.in_(("queued", "in_progress"))).all()
    for t in {x.id: x for x in never + open_}.values():
        cur = current(db, t.id)
        if cur is None or cur.source_key != source_key(db, t) or cur.status != "ready":
            if refresh(db, t) is not None:
                n += 1
    db.commit()
    return n
