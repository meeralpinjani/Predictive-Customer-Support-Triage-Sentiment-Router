"""Summaries, handovers and conversation recovery.

- Summary: customers get only customer-facing fields; agents and admins get everything for tickets
  they may see. Status is always explicit: ready | stale | pending | failed | unavailable.
- Handovers: agents and admins only (403 for customers, 404 for tickets the agent can't see).
- Recovery: missed messages after a known id, and a resume payload for reconnects and refreshes.
  Nothing here ever creates a ticket.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.auth import AGENT_ROLES, check_rate_limit, current_user, require
from app.config import settings
from app.db import get_db
from app.models import Handover, Message, Ticket, User
from app.schemas import MessageOut
from app.services import handover as handovers
from app.services import summarization as sm
from app.services.triage import serialise, serialise_for_customer, serialise_message

router = APIRouter(prefix="/api", tags=["conversation"])
MAX_PAGE = 200


class SummaryOut(BaseModel):
    ticket_id: int
    status: str                      # ready | stale | pending | failed | unavailable
    reason: str | None = None
    latest_message_id: int | None = None
    summary: dict | None = None      # the last good summary (customers: customer-facing fields only)


class SummaryStatusOut(BaseModel):
    ticket_id: int
    status: str
    revision: int | None = None
    method: str | None = None
    updated_at: datetime | None = None
    latest_message_id: int | None = None


def _ticket(db: Session, ticket_id: int, user: User) -> Ticket:
    from app.api.tickets import _viewable
    return _viewable(db, ticket_id, user)        # same 404 for "not yours" and "doesn't exist"


def _summary_out(db: Session, t: Ticket, user: User) -> SummaryOut:
    st = sm.state(db, t)
    return SummaryOut(ticket_id=t.id, status=st["status"], reason=st["reason"],
                      latest_message_id=sm.last_message_id(db, t.id),
                      summary=sm.view(st["summary"], customer=user.role == "customer"))


def _after(db: Session, t: Ticket, after_id: int | None, limit: int | None) -> list[Message]:
    q = db.query(Message).filter(Message.ticket_id == t.id)
    if after_id is not None:
        anchor = db.get(Message, after_id)
        if anchor is None or anchor.ticket_id != t.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found on this ticket")
        q = q.filter(or_(Message.created_at > anchor.created_at,
                         and_(Message.created_at == anchor.created_at, Message.id > anchor.id)))
    q = q.order_by(Message.created_at, Message.id)
    return q.limit(limit).all() if limit else q.all()


# ---------------------------------------------------------------- summaries
@router.get("/tickets/{ticket_id}/summary", response_model=SummaryOut)
def get_summary(ticket_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> SummaryOut:
    return _summary_out(db, _ticket(db, ticket_id, user), user)


@router.get("/tickets/{ticket_id}/summary/status", response_model=SummaryStatusOut)
def summary_status(ticket_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> SummaryStatusOut:
    t = _ticket(db, ticket_id, user)
    st = sm.state(db, t)
    cur = st.get("current")
    return SummaryStatusOut(ticket_id=t.id, status=st["status"], revision=cur.revision if cur else None,
                            method=cur.method if cur else None, updated_at=cur.updated_at if cur else None,
                            latest_message_id=sm.last_message_id(db, t.id))


@router.post("/tickets/{ticket_id}/summary/refresh", response_model=SummaryOut, status_code=status.HTTP_202_ACCEPTED)
def refresh_summary(ticket_id: int, user: User = Depends(require(*AGENT_ROLES, "admin")),
                    db: Session = Depends(get_db)) -> SummaryOut:
    """Rebuild now if anything changed (idempotent: an up-to-date summary is returned as it is)."""
    t = _ticket(db, ticket_id, user)
    if not settings.ticket_summary_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Summaries are turned off (TICKET_SUMMARY_ENABLED)")
    check_rate_limit(f"summary-refresh:{t.id}", limit=settings.ticket_summary_refresh_per_hour, window_sec=3600)
    sm.refresh(db, t)
    db.commit()
    return _summary_out(db, t, user)


# ---------------------------------------------------------------- recovery
@router.get("/tickets/{ticket_id}/messages/since/{message_id}", response_model=list[MessageOut])
def messages_since(ticket_id: int, message_id: int, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> list[MessageOut]:
    """Saved messages after the last one the client has (for reconnects)."""
    t = _ticket(db, ticket_id, user)
    return [serialise_message(m, db, user) for m in _after(db, t, message_id, MAX_PAGE)]


@router.post("/tickets/{ticket_id}/resume")
def resume(ticket_id: int, recent: int = Query(50, ge=1, le=MAX_PAGE), user: User = Depends(current_user),
           db: Session = Depends(get_db)) -> dict:
    """Everything a client needs to continue the same ticket after a disconnect or refresh."""
    t = _ticket(db, ticket_id, user)
    rows = (db.query(Message).filter(Message.ticket_id == t.id)
            .order_by(Message.created_at.desc(), Message.id.desc()).limit(recent).all())
    msgs = [serialise_message(m, db, user) for m in reversed(rows)]
    st = sm.state(db, t)
    cur = st.get("current")
    total = db.query(Message).filter(Message.ticket_id == t.id).count()
    return {
        "ticket": serialise_for_customer(t, db) if user.role == "customer" else serialise(t, db),
        "messages": msgs,
        "has_earlier": total > len(msgs),
        "cursor": msgs[-1].id if msgs else None,
        "summary": {"status": st["status"], "revision": cur.revision if cur else None,
                    "updated_at": cur.updated_at if cur else None},
    }


# ---------------------------------------------------------------- handovers (staff only)
@router.get("/tickets/{ticket_id}/handovers")
def list_handovers(ticket_id: int, user: User = Depends(require(*AGENT_ROLES, "admin")),
                   db: Session = Depends(get_db)) -> list[dict]:
    t = _ticket(db, ticket_id, user)
    rows = db.query(Handover).filter(Handover.ticket_id == t.id).order_by(Handover.sequence.desc()).all()
    return [handovers.view(h, db) for h in rows]


@router.get("/tickets/{ticket_id}/handovers/{handover_id}")
def get_handover(ticket_id: int, handover_id: int, user: User = Depends(require(*AGENT_ROLES, "admin")),
                 db: Session = Depends(get_db)) -> dict:
    t = _ticket(db, ticket_id, user)
    h = db.get(Handover, handover_id)
    if h is None or h.ticket_id != t.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Handover not found")
    return handovers.view(h, db)
