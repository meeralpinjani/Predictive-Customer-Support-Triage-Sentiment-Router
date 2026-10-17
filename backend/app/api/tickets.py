from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Feedback, Ticket
from app.schemas import FeedbackIn, OverrideIn, TicketIn, TicketOut
from app.services.rescore import rescore_open
from app.services.triage import process_ticket, serialise

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def submit_ticket(
    payload: TicketIn,
    db: Session = Depends(get_db),
) -> TicketOut:
    ticket = process_ticket(db, payload)
    return serialise(ticket, db)


@router.get("", response_model=list[TicketOut])
def list_tickets(
    route: str | None = Query(None, description="Filter by route"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    sort: str = Query("priority", description="Sort order: priority or fcfs"),
    db: Session = Depends(get_db),
) -> list[TicketOut]:
    # Ageing: Re-score open tickets on every list call
    rescore_open(db)

    query = db.query(Ticket)

    if route:
        query = query.filter(Ticket.route == route)
    if status_filter:
        query = query.filter(Ticket.status == status_filter)

    if sort.lower() == "fcfs":
        query = query.order_by(Ticket.created_at.asc())
    else:
        # Priority sort: highest priority first, ties broken by longest wait (earliest created)
        query = query.order_by(Ticket.priority.desc(), Ticket.created_at.asc())

    tickets = query.all()
    return [serialise(t, db) for t in tickets]


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
) -> TicketOut:
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )
    return serialise(ticket, db)


@router.post("/{ticket_id}/override", response_model=TicketOut)
def override_ticket(
    ticket_id: int,
    payload: OverrideIn,
    db: Session = Depends(get_db),
) -> TicketOut:
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    old_route = ticket.route
    if payload.route:
        ticket.route = payload.route
        ticket.route_reason = f"Agent override: {payload.reason}"
    if payload.priority is not None:
        ticket.priority = payload.priority

    ticket.route_locked = True

    feedback = Feedback(
        ticket_id=ticket.id,
        kind="override",
        old_route=old_route,
        new_route=ticket.route,
        reason=payload.reason,
    )
    db.add(feedback)
    db.commit()
    db.refresh(ticket)
    return serialise(ticket, db)


@router.post("/{ticket_id}/resolve", response_model=TicketOut)
def resolve_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
) -> TicketOut:
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    ticket.status = "resolved"
    feedback = Feedback(
        ticket_id=ticket.id,
        kind="resolved",
        reason="Resolved by agent",
    )
    db.add(feedback)
    db.commit()
    db.refresh(ticket)
    return serialise(ticket, db)


@router.post("/{ticket_id}/feedback", response_model=TicketOut)
def submit_feedback(
    ticket_id: int,
    payload: FeedbackIn,
    db: Session = Depends(get_db),
) -> TicketOut:
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    helpful = None
    if payload.kind == "kb_helpful":
        helpful = True
    elif payload.kind == "kb_not_helpful":
        helpful = False
        # If automated routine reply was unhelpful, re-queue to human tier
        if ticket.status == "kb_handled":
            ticket.status = "queued"
            ticket.route = "tier1"
            ticket.kb_action = "none"
            ticket.route_reason = "Escalated to human after unhelpful KB"

    feedback = Feedback(
        ticket_id=ticket.id,
        kind=payload.kind,
        reason=payload.note,
        helpful=helpful,
    )
    db.add(feedback)
    db.commit()
    db.refresh(ticket)
    return serialise(ticket, db)
