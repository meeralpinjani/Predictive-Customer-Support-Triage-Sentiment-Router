"""Ticket endpoints. Every route checks who is asking:

- customers create tickets and only ever see their own (no internal scores);
- Level 1-3 agents work the queue of their level, claim, reply, escalate and resolve;
- admins see everything and can override routing or priority.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import events
from app.auth import AGENT_ROLES, current_user, is_agent, require
from app.categories import CATEGORY_BY_ID
from app.db import get_db
from app.models import Attachment, CallbackRequest, Customer, Feedback, Message, Ticket, User
from app.schemas import (
    CallbackIn, CallbackOut, CallbackPatch, CustomerTicketOut, EscalateIn, FeedbackIn, MessageIn, MessageOut,
    OverrideIn, TicketIn, TicketOut,
)
from app.services.files import attachment_out, path_for, save_uploads
from app.services.knowledge import guides_for_ticket
from app.services.replies import suggested_reply
from app.services.router import LEVEL, Decision
from app.services.triage import (
    OPEN, add_system_message, agent_reply, customer_reply, escalate_after_kb, escalate_manually, process_ticket,
    rebalance, route_ticket, serialise, serialise_for_customer, serialise_message,
)

router = APIRouter(prefix="/api", tags=["tickets"])


# ---------------------------------------------------------------- access helpers
def _get(db: Session, ticket_id: int) -> Ticket:
    t = db.get(Ticket, ticket_id)
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Ticket {ticket_id} not found")
    return t


def can_view(user: User, t: Ticket) -> bool:
    if user.role == "admin":
        return True
    if user.role == "customer":
        return user.customer_id is not None and t.customer_id == user.customer_id
    return t.route == user.role or t.assigned_agent_id == user.id


def can_work(user: User, t: Ticket) -> bool:
    """Agents act on tickets currently at their level; admins on anything."""
    return user.role == "admin" or (is_agent(user) and t.route == user.role)


def _viewable(db: Session, ticket_id: int, user: User) -> Ticket:
    t = _get(db, ticket_id)
    if not can_view(user, t):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Ticket {ticket_id} not found")
    return t


def _workable(db: Session, ticket_id: int, user: User) -> Ticket:
    t = _viewable(db, ticket_id, user)
    if not can_work(user, t):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This ticket is not at your level")
    return t


def _conflict(msg: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, msg)


def _publish(kind: str, t: Ticket, old_route: str | None = None, **extra) -> None:
    events.publish(events.ticket_event(kind, t, old_route=old_route, **extra))


def _publish_route_change(t: Ticket, old: str) -> None:
    if old != t.route:
        _publish("ticket.escalated", t, old_route=old, reason=t.route_reason)


# ---------------------------------------------------------------- create & list
@router.post("/tickets", status_code=status.HTTP_201_CREATED)
def submit_ticket(payload: TicketIn, user: User = Depends(require("customer", "admin")),
                  db: Session = Depends(get_db)) -> TicketOut | CustomerTicketOut:
    if payload.category not in CATEGORY_BY_ID:
        raise HTTPException(422, f"Unknown category '{payload.category}'")
    if user.role == "customer":
        customer = db.get(Customer, user.customer_id) if user.customer_id else None
        if customer is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your account has no customer profile")
    else:
        customer = db.get(Customer, payload.customer_id) if payload.customer_id else None
        if payload.customer_id and customer is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown customer '{payload.customer_id}'")
    t = process_ticket(db, payload, customer, created_by=user)
    _publish("ticket.created", t)
    return serialise_for_customer(t, db) if user.role == "customer" else serialise(t, db)


@router.get("/my/tickets", response_model=list[CustomerTicketOut])
def my_tickets(user: User = Depends(require("customer")), db: Session = Depends(get_db)) -> list[CustomerTicketOut]:
    rows = db.query(Ticket).filter(Ticket.customer_id == user.customer_id).order_by(Ticket.updated_at.desc()).all()
    return [serialise_for_customer(t, db) for t in rows]


@router.get("/my/tickets/{ticket_id}", response_model=CustomerTicketOut)
def my_ticket(ticket_id: int, user: User = Depends(require("customer")), db: Session = Depends(get_db)) -> CustomerTicketOut:
    return serialise_for_customer(_viewable(db, ticket_id, user), db)


@router.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    view: str = Query("queue", description="Agents: queue | mine | resolved. Admins: all"),
    route: str | None = Query(None, description="Admins: filter by level"),
    status_filter: str | None = Query(None, alias="status"),
    sort: str = Query("priority", description="priority or fcfs"),
    user: User = Depends(require(*AGENT_ROLES, "admin")),
    db: Session = Depends(get_db),
) -> list[TicketOut]:
    # Read-only: ageing is applied by the background re-scorer (see app.main).
    q = db.query(Ticket)
    if user.role == "admin":
        if route:
            q = q.filter(Ticket.route == route)
        if status_filter:
            q = q.filter(Ticket.status == status_filter)
    elif view == "mine":
        q = q.filter(Ticket.assigned_agent_id == user.id, Ticket.status.in_(OPEN))
    elif view == "resolved":
        q = q.filter(Ticket.assigned_agent_id == user.id, Ticket.status == "resolved")
    else:
        q = q.filter(Ticket.route == user.role, Ticket.status.in_(OPEN))
    q = q.order_by(Ticket.created_at.asc()) if sort.lower() == "fcfs" else \
        q.order_by(Ticket.priority.desc(), Ticket.created_at.asc())
    return [serialise(t, db) for t in q.all()]


@router.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, user: User = Depends(require(*AGENT_ROLES, "admin")),
               db: Session = Depends(get_db)) -> TicketOut:
    return serialise(_viewable(db, ticket_id, user), db)


# ---------------------------------------------------------------- agent actions
@router.post("/tickets/{ticket_id}/claim", response_model=TicketOut)
def claim(ticket_id: int, user: User = Depends(require(*AGENT_ROLES)), db: Session = Depends(get_db)) -> TicketOut:
    t = _workable(db, ticket_id, user)
    if t.status not in OPEN:
        raise _conflict(f"Ticket is {t.status}")
    t.status, t.assigned_agent_id = "in_progress", user.id
    add_system_message(db, t, f"{user.name} is working on this ticket.")
    db.commit()
    _publish("ticket.updated", t)
    return serialise(t, db)


@router.post("/tickets/{ticket_id}/escalate", response_model=TicketOut)
def escalate(ticket_id: int, payload: EscalateIn, user: User = Depends(require(*AGENT_ROLES, "admin")),
             db: Session = Depends(get_db)) -> TicketOut:
    t = _workable(db, ticket_id, user)
    if t.status not in OPEN:
        raise _conflict(f"Ticket is {t.status}")
    try:
        old = escalate_manually(db, t, user, payload.reason)
    except ValueError as exc:
        raise _conflict(str(exc))
    db.add(Feedback(ticket_id=t.id, user_id=user.id, kind="escalate", old_route=old, new_route=t.route,
                    reason=payload.reason))
    db.commit()
    _publish_route_change(t, old)
    return serialise(t, db)


@router.post("/tickets/{ticket_id}/override", response_model=TicketOut)
def override_ticket(ticket_id: int, payload: OverrideIn, user: User = Depends(require("admin")),
                    db: Session = Depends(get_db)) -> TicketOut:
    t = _get(db, ticket_id)
    if t.status not in OPEN:
        raise _conflict(f"Ticket is {t.status}; only open tickets can be overridden")
    if payload.route is None and payload.priority is None:
        raise HTTPException(422, "Give a new level, a new priority, or both")
    old = t.route
    if payload.route:
        route_ticket(db, t, Decision(payload.route, f"Admin override: {payload.reason}", t.kb_action))
        t.route_locked = True
    if payload.priority is not None:
        t.priority, t.priority_locked = payload.priority, True
    db.add(Feedback(ticket_id=t.id, user_id=user.id, kind="override", old_route=old, new_route=t.route,
                    reason=payload.reason))
    db.commit()
    _publish_route_change(t, old)
    _publish("ticket.updated", t)
    return serialise(t, db)


@router.post("/tickets/{ticket_id}/resolve")
def resolve_ticket(ticket_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = _viewable(db, ticket_id, user)
    if user.role != "customer" and not can_work(user, t) and t.assigned_agent_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This ticket is not at your level")
    if t.status == "resolved":
        raise _conflict("Ticket is already resolved")
    t.status, t.resolved_at = "resolved", datetime.now(timezone.utc)
    if user.role != "customer" and t.assigned_agent_id is None:
        t.assigned_agent_id = user.id
    who = "the customer" if user.role == "customer" else user.name
    add_system_message(db, t, f"Resolved by {who}.")
    if t.route in LEVEL:
        db.flush()
        rebalance(db, t.route)
    db.add(Feedback(ticket_id=t.id, user_id=user.id, kind="resolved", reason=f"Resolved by {who}"))
    db.commit()
    _publish("ticket.resolved", t)
    return serialise_for_customer(t, db) if user.role == "customer" else serialise(t, db)


# ---------------------------------------------------------------- customer feedback on auto-answers
@router.post("/tickets/{ticket_id}/feedback", response_model=CustomerTicketOut)
def submit_feedback(ticket_id: int, payload: FeedbackIn, user: User = Depends(require("customer")),
                    db: Session = Depends(get_db)) -> CustomerTicketOut:
    t = _viewable(db, ticket_id, user)
    if t.route != "auto_kb":
        raise _conflict("This ticket has no automatic answer to rate")
    if t.kb_rated:
        raise _conflict("The answer was already rated")
    t.kb_rated = True
    helpful = payload.kind == "kb_helpful"
    old = t.route
    if helpful:
        t.status, t.resolved_at = "resolved", datetime.now(timezone.utc)
        add_system_message(db, t, "The customer confirmed the automatic answer solved it.")
    else:
        old = escalate_after_kb(db, t)
    db.add(Feedback(ticket_id=t.id, user_id=user.id, kind=payload.kind, reason=payload.note, helpful=helpful))
    db.commit()
    if helpful:
        _publish("ticket.resolved", t)
    else:
        _publish_route_change(t, old)
    return serialise_for_customer(t, db)


# ---------------------------------------------------------------- conversation (live chat)
@router.get("/tickets/{ticket_id}/messages", response_model=list[MessageOut])
def list_messages(ticket_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[MessageOut]:
    t = _viewable(db, ticket_id, user)
    rows = db.query(Message).filter(Message.ticket_id == t.id).order_by(Message.created_at, Message.id).all()
    return [serialise_message(m, db, user) for m in rows]


@router.post("/tickets/{ticket_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def post_message(ticket_id: int, payload: MessageIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> MessageOut:
    t = _viewable(db, ticket_id, user)
    body = payload.body.strip()
    if user.role == "customer":
        msg, old = customer_reply(db, t, user, body)
    else:
        if not can_work(user, t) and t.assigned_agent_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This ticket is not at your level")
        msg, old = agent_reply(db, t, user, body), t.route
    db.commit()
    db.refresh(msg)
    out = serialise_message(msg, db, user)
    events.publish({**events.ticket_event("message.created", t), "actor_id": user.id,
                    "author_role": user.role, "preview": body[:120]})
    _publish_route_change(t, old)
    return out


@router.post("/tickets/{ticket_id}/typing")
def typing(ticket_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    t = _viewable(db, ticket_id, user)
    name = user.name if user.role == "customer" else user.name.split()[0]
    events.publish({**events.ticket_event("typing", t), "actor_id": user.id, "name": name, "author_role": user.role})
    return {"ok": True}


# ---------------------------------------------------------------- Level 3 callback requests
def _cb_out(c: CallbackRequest) -> CallbackOut:
    return CallbackOut(id=c.id, phone=c.phone, preferred_time=c.preferred_time, note=c.note, status=c.status,
                       created_at=c.created_at)


@router.get("/tickets/{ticket_id}/callbacks", response_model=list[CallbackOut])
def list_callbacks(ticket_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[CallbackOut]:
    t = _viewable(db, ticket_id, user)
    rows = db.query(CallbackRequest).filter(CallbackRequest.ticket_id == t.id).order_by(CallbackRequest.created_at).all()
    return [_cb_out(c) for c in rows]


@router.post("/tickets/{ticket_id}/callbacks", response_model=CallbackOut, status_code=status.HTTP_201_CREATED)
def request_callback(ticket_id: int, payload: CallbackIn, user: User = Depends(require("customer")),
                     db: Session = Depends(get_db)) -> CallbackOut:
    t = _viewable(db, ticket_id, user)
    if t.route != "level3":
        raise _conflict("Calls are available once a ticket reaches Expert Escalation")
    if t.status == "resolved":
        raise _conflict("This ticket is resolved")
    if db.query(CallbackRequest).filter(CallbackRequest.ticket_id == t.id, CallbackRequest.status != "done").count():
        raise _conflict("A call is already requested for this ticket")
    cb = CallbackRequest(ticket_id=t.id, phone=payload.phone.strip(), preferred_time=payload.preferred_time.strip(),
                         note=payload.note.strip())
    db.add(cb)
    add_system_message(db, t, f"Callback requested{(' for ' + cb.preferred_time) if cb.preferred_time else ''}.")
    db.commit()
    db.refresh(cb)
    _publish("callback.requested", t)
    return _cb_out(cb)


@router.patch("/tickets/{ticket_id}/callbacks/{callback_id}", response_model=CallbackOut)
def update_callback(ticket_id: int, callback_id: int, payload: CallbackPatch,
                    user: User = Depends(require("level3", "admin")), db: Session = Depends(get_db)) -> CallbackOut:
    t = _workable(db, ticket_id, user)
    cb = db.get(CallbackRequest, callback_id)
    if not cb or cb.ticket_id != t.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Callback not found")
    cb.status = payload.status
    label = {"scheduled": "Call scheduled", "done": "Call completed", "requested": "Call re-opened"}[payload.status]
    add_system_message(db, t, f"{label} by {user.name.split()[0]}.")
    db.commit()
    _publish("callback.updated", t)
    return _cb_out(cb)


# ---------------------------------------------------------------- attachments
def _can_post(user: User, t: Ticket) -> bool:
    return user.role == "customer" or can_work(user, t) or t.assigned_agent_id == user.id


@router.post("/tickets/{ticket_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_ticket_files(ticket_id: int, files: list[UploadFile] = File(...),
                              user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    """Files that belong to the ticket itself (e.g. screenshots attached when creating it)."""
    t = _viewable(db, ticket_id, user)
    if not _can_post(user, t):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This ticket is not at your level")
    saved = await save_uploads(db, files, t.id, user.id)
    db.commit()
    _publish("ticket.updated", t)
    return [attachment_out(a) for a in saved]


@router.post("/tickets/{ticket_id}/messages/upload", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def post_message_with_files(ticket_id: int, files: list[UploadFile] = File(...), body: str = Form(""),
                                  user: User = Depends(current_user), db: Session = Depends(get_db)) -> MessageOut:
    """A chat message with screenshots / PDFs (the text is optional)."""
    t = _viewable(db, ticket_id, user)
    if not _can_post(user, t):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This ticket is not at your level")
    text = body.strip()[:4000] or f"Sent {len(files)} file{'s' if len(files) != 1 else ''}"
    if user.role == "customer":
        msg, old = customer_reply(db, t, user, text)
    else:
        msg, old = agent_reply(db, t, user, text), t.route
    db.flush()
    await save_uploads(db, files, t.id, user.id, message_id=msg.id)
    db.commit()
    db.refresh(msg)
    events.publish({**events.ticket_event("message.created", t), "actor_id": user.id,
                    "author_role": user.role, "preview": text[:120]})
    _publish_route_change(t, old)
    return serialise_message(msg, db, user)


@router.get("/attachments/{attachment_id}")
def download_attachment(attachment_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    att = db.get(Attachment, attachment_id)
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    _viewable(db, att.ticket_id, user)   # same rule as the ticket: 404 if you can't see it
    path = path_for(att)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return FileResponse(path, media_type=att.content_type, filename=att.filename,
                        content_disposition_type="inline" if att.content_type.startswith("image/") else "attachment",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"})


# ---------------------------------------------------------------- agent helpers
@router.get("/tickets/{ticket_id}/suggested-reply")
def get_suggested_reply(ticket_id: int, user: User = Depends(require(*AGENT_ROLES, "admin")),
                        db: Session = Depends(get_db)) -> dict:
    return suggested_reply(db, _viewable(db, ticket_id, user), user)


@router.get("/tickets/{ticket_id}/guides")
def get_guides(ticket_id: int, user: User = Depends(require(*AGENT_ROLES, "admin")),
               db: Session = Depends(get_db)) -> list[dict]:
    return guides_for_ticket(db, _viewable(db, ticket_id, user))
