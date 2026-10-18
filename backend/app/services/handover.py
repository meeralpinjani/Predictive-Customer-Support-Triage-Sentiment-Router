"""Handover snapshots: when a ticket moves to another support level or another agent, freeze what the
next person needs to know, in the SAME transaction as the transfer. See docs/summaries/DECISIONS.md.

- Built from a fresh extractive summary (milliseconds, no language model). If that fails or summaries
  are turned off, it falls back to references to the raw recent messages ("fallback_raw").
- The transfer never fails because of a handover: creation runs in a savepoint and errors are logged.
- Immutable: an ORM guard refuses any UPDATE. Corrections are new rows with supersedes_id.
- Never changes priority, reply-by time, emergency flags, route locks, level or assignment.
- Created for: level changes (agent/automatic escalation, admin override) and agent-to-agent
  reassignment of a ticket that already had a support reply. Not for routine first assignment.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import event, func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Handover, Message, Ticket, User

log = logging.getLogger("triage.handover")
SNAPSHOT_FIELDS = ("problem_statement", "confirmed_facts", "customer_claims", "troubleshooting_attempted",
                   "successful_actions", "failed_attempts", "pending_actions", "promises_made",
                   "unresolved_questions", "next_recommended_step", "escalation_reason")
TRIGGERS = ("escalation", "reassignment", "admin_override", "reopen")


@event.listens_for(Handover, "before_update")
def _immutable(mapper, connection, target):
    raise RuntimeError("Handovers are immutable: create a new handover with supersedes_id instead")


def _message_refs(db: Session, t: Ticket, limit: int = 20) -> list[dict]:
    rows = (db.query(Message).filter(Message.ticket_id == t.id, Message.kind == "message")
            .order_by(Message.created_at.desc(), Message.id.desc()).limit(limit).all())
    return [{"id": m.id, "from": m.author_role, "at": m.created_at.isoformat()} for m in reversed(rows)]


def create(db: Session, t: Ticket, trigger: str, *, from_agent_id: int | None, from_level: str | None,
           to_agent_id: int | None, to_level: str | None, reason: str = "", actor_id: int | None = None,
           supersedes_id: int | None = None) -> Handover | None:
    """Insert one handover inside the caller's transaction. Never raises."""
    from app.services import summarization as sm
    try:
        db.flush()   # include messages saved earlier in this transaction
        method, source_revision, error, summary = "extractive", None, None, {}
        if not settings.ticket_summary_enabled:
            method, error = "fallback_raw", "summaries_disabled"
        else:
            try:
                summary = sm.extractive(db, t)
                row = sm.write_revision(db, t, summary, "ready", "extractive")
                source_revision = row.revision if row else None
            except Exception as exc:
                method, error, summary = "fallback_raw", type(exc).__name__, {}
        actor = db.get(User, actor_id) if actor_id else None
        snapshot = {
            "ticket_id": t.id, "trigger": trigger, "reason": reason[:500],
            "from": {"agent_id": from_agent_id, "level": from_level},
            "to": {"agent_id": to_agent_id, "level": to_level},
            "actor": actor.name if actor else "automatic",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "summary_revision": source_revision, "method": method,
            # Copied from the ticket at transfer time, labelled as such (never recomputed here).
            "at_transfer": {"priority": t.priority, "critical_flags": [f for f in (t.critical_flags or "").split(",") if f],
                            "status": t.status, "reply_by_minutes": t.sla_minutes},
            **{k: summary.get(k) for k in SNAPSHOT_FIELDS},
            "last_included_message_id": summary.get("last_included_message_id") if summary else
            (_message_refs(db, t, 1) or [{}])[-1].get("id"),
            "messages": _message_refs(db, t),
        }
        seq = (db.query(func.max(Handover.sequence)).filter(Handover.ticket_id == t.id).scalar() or 0) + 1
        h = Handover(ticket_id=t.id, sequence=seq, from_agent_id=from_agent_id, from_level=from_level,
                     to_agent_id=to_agent_id, to_level=to_level, trigger=trigger, reason=reason[:500],
                     actor_id=actor_id, source_revision=source_revision, snapshot=json.dumps(snapshot, default=str),
                     snapshot_method=method, error=error, supersedes_id=supersedes_id)
        with db.begin_nested():
            db.add(h)
        db.info.setdefault("after_commit_events", []).append(("handover.created", t.id))
        return h
    except Exception as exc:   # the transfer itself must always go through
        log.warning("Handover not recorded for ticket %s: %s", t.id, type(exc).__name__)
        return None


def latest(db: Session, ticket_id: int) -> Handover | None:
    return db.query(Handover).filter(Handover.ticket_id == ticket_id).order_by(Handover.sequence.desc()).first()


def view(h: Handover, db: Session) -> dict:
    names = {u.id: u.name for u in db.query(User).filter(User.id.in_([x for x in (h.from_agent_id, h.to_agent_id, h.actor_id) if x])).all()}
    return {"id": h.id, "ticket_id": h.ticket_id, "sequence": h.sequence, "trigger": h.trigger, "reason": h.reason,
            "from_agent": names.get(h.from_agent_id), "from_level": h.from_level,
            "to_agent": names.get(h.to_agent_id), "to_level": h.to_level,
            "actor": names.get(h.actor_id, "automatic"), "source_revision": h.source_revision,
            "snapshot_method": h.snapshot_method, "error": h.error, "supersedes_id": h.supersedes_id,
            "created_at": h.created_at, "snapshot": json.loads(h.snapshot or "{}")}
