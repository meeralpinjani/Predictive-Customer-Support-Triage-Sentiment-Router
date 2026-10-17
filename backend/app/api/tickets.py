from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Customer, Feedback, Ticket
from app.schemas import FeedbackIn, OverrideIn, TicketIn, TicketOut
from app.services.triage import OPEN, escalate_after_kb, process_ticket, route_ticket, serialise
from app.services.router import Decision

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _get(db: Session, ticket_id: int) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Ticket {ticket_id} not found")
    return ticket


def _conflict(msg: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, msg)


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def submit_ticket(payload: TicketIn, db: Session = Depends(get_db)) -> TicketOut:
    if payload.customer_id and not db.get(Customer, payload.customer_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown customer '{payload.customer_id}'")
    return serialise(process_ticket(db, payload), db)


@router.get("", response_model=list[TicketOut])
def list_tickets(
    route: str | None = Query(None, description="Filter by route"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    sort: str = Query("priority", description="Sort order: priority or fcfs"),
    db: Session = Depends(get_db),
) -> list[TicketOut]:
    # Read-only: ageing is applied by the background re-scorer (see app.main).
    query = db.query(Ticket)
    if route:
        query = query.filter(Ticket.route == route)
    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    if sort.lower() == "fcfs":
        query = query.order_by(Ticket.created_at.asc())
    else:
        # Highest priority first; ties go to whoever has waited longest.
        query = query.order_by(Ticket.priority.desc(), Ticket.created_at.asc())
    return [serialise(t, db) for t in query.all()]


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)) -> TicketOut:
    return serialise(_get(db, ticket_id), db)


@router.post("/{ticket_id}/override", response_model=TicketOut)
def override_ticket(ticket_id: int, payload: OverrideIn, db: Session = Depends(get_db)) -> TicketOut:
    ticket = _get(db, ticket_id)
    if ticket.status not in OPEN:
        raise _conflict(f"Ticket is {ticket.status}; only open tickets can be overridden")
    if payload.route is None and payload.priority is None:
        raise HTTPException(422, "Give a new route, a new priority, or both")

    old_route = ticket.route
    if payload.route:
        route_ticket(db, ticket, Decision(payload.route, f"Agent override: {payload.reason}", ticket.kb_action))
        ticket.route_locked = True
    if payload.priority is not None:
        ticket.priority = payload.priority
        ticket.priority_locked = True

    db.add(Feedback(ticket_id=ticket.id, kind="override", old_route=old_route, new_route=ticket.route,
                    reason=payload.reason))
    db.commit()
    db.refresh(ticket)
    return serialise(ticket, db)


@router.post("/{ticket_id}/resolve", response_model=TicketOut)
def resolve_ticket(ticket_id: int, db: Session = Depends(get_db)) -> TicketOut:
    ticket = _get(db, ticket_id)
    if ticket.status == "resolved":
        raise _conflict("Ticket is already resolved")
    ticket.status = "resolved"
    ticket.resolved_at = datetime.now(timezone.utc)
    db.add(Feedback(ticket_id=ticket.id, kind="resolved", reason="Resolved by agent"))
    db.commit()
    db.refresh(ticket)
    return serialise(ticket, db)


@router.post("/{ticket_id}/feedback", response_model=TicketOut)
def submit_feedback(ticket_id: int, payload: FeedbackIn, db: Session = Depends(get_db)) -> TicketOut:
    ticket = _get(db, ticket_id)

    helpful = None
    if payload.kind in ("kb_helpful", "kb_not_helpful"):
        if ticket.kb_action == "none" and ticket.status != "kb_handled":
            raise _conflict("This ticket has no knowledge-base answer to rate")
        if ticket.kb_rated:
            raise _conflict("The knowledge-base answer was already rated")
        ticket.kb_rated = True
        helpful = payload.kind == "kb_helpful"
        if ticket.status == "kb_handled":
            if helpful:
                ticket.status = "resolved"
                ticket.resolved_at = datetime.now(timezone.utc)
            else:
                escalate_after_kb(db, ticket)

    db.add(Feedback(ticket_id=ticket.id, kind=payload.kind, reason=payload.note, helpful=helpful))
    db.commit()
    db.refresh(ticket)
    return serialise(ticket, db)
