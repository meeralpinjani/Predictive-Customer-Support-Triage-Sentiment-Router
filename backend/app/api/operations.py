"""Incidents (grouped duplicate tickets), analytics over time, the email outbox and retraining."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import events
from app.auth import AGENT_ROLES, require
from app.db import get_db
from app.models import Incident, OutboxEmail, Ticket, User
from app.schemas import IncidentIn, IncidentMessageIn, RetrainApplyIn
from app.services import incidents as inc_svc
from app.services import retrain
from app.services.analytics import analytics
from app.services.mailer import gmail_configured

router = APIRouter(prefix="/api", tags=["operations"])
STAFF = (*AGENT_ROLES, "admin")


def _incident_out(db: Session, inc: Incident) -> dict:
    tickets = inc_svc.linked(db, inc)
    return {
        "id": inc.id, "title": inc.title, "status": inc.status, "created_at": inc.created_at,
        "resolved_at": inc.resolved_at,
        "tickets": [{"id": t.id, "subject": t.subject or t.body[:80], "status": t.status, "route": t.route,
                     "priority": t.priority} for t in tickets],
        "open": sum(1 for t in tickets if t.status in ("queued", "in_progress")),
    }


def _get_incident(db: Session, incident_id: int, user: User) -> Incident:
    inc = db.get(Incident, incident_id)
    if not inc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    if user.role != "admin":
        tickets = inc_svc.linked(db, inc)
        if not any(t.route == user.role or t.assigned_agent_id == user.id for t in tickets):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    return inc


@router.get("/incidents/suggestions")
def incident_suggestions(user: User = Depends(require(*STAFF)), db: Session = Depends(get_db)) -> dict:
    return inc_svc.suggestions(db, user)


@router.get("/incidents")
def list_incidents(user: User = Depends(require(*STAFF)), db: Session = Depends(get_db)) -> list[dict]:
    out = []
    for inc in db.query(Incident).order_by(Incident.status, Incident.created_at.desc()).limit(50).all():
        data = _incident_out(db, inc)
        if user.role == "admin" or any(t["route"] == user.role for t in data["tickets"]):
            out.append(data)
    return out


@router.post("/incidents", status_code=status.HTTP_201_CREATED)
def create_incident(payload: IncidentIn, user: User = Depends(require(*STAFF)), db: Session = Depends(get_db)) -> dict:
    tickets = db.query(Ticket).filter(Ticket.id.in_(payload.ticket_ids)).all()
    if len(tickets) != len(set(payload.ticket_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Some tickets were not found")
    for t in tickets:
        if user.role != "admin" and not (t.route == user.role or t.assigned_agent_id == user.id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Ticket #{t.id} is not at your level")
        if t.incident_id:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Ticket #{t.id} already belongs to incident #{t.incident_id}")
    inc = inc_svc.create(db, user, payload.ticket_ids, payload.title.strip())
    for t in tickets:
        events.publish(events.ticket_event("ticket.updated", t))
    return _incident_out(db, inc)


@router.post("/incidents/{incident_id}/reply")
def incident_reply(incident_id: int, payload: IncidentMessageIn, user: User = Depends(require(*STAFF)),
                   db: Session = Depends(get_db)) -> dict:
    inc = _get_incident(db, incident_id, user)
    if not payload.body.strip():
        raise HTTPException(422, "Write a message")
    targets = inc_svc.reply_all(db, inc, user, payload.body.strip())
    for t in targets:
        events.publish({**events.ticket_event("message.created", t), "actor_id": user.id, "author_role": user.role,
                        "preview": payload.body[:120]})
    return {**_incident_out(db, inc), "replied_to": len(targets)}


@router.post("/incidents/{incident_id}/resolve")
def incident_resolve(incident_id: int, payload: IncidentMessageIn, user: User = Depends(require(*STAFF)),
                     db: Session = Depends(get_db)) -> dict:
    inc = _get_incident(db, incident_id, user)
    if inc.status == "resolved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Incident already resolved")
    targets = inc_svc.resolve(db, inc, user, payload.body.strip())
    for t in targets:
        events.publish(events.ticket_event("ticket.resolved", t))
    return {**_incident_out(db, inc), "resolved_tickets": len(targets)}


# ---------------------------------------------------------------- admin
@router.get("/admin/analytics")
def get_analytics(days: int = Query(7, ge=1, le=30), _: User = Depends(require("admin")),
                  db: Session = Depends(get_db)) -> dict:
    return analytics(db, days)


@router.get("/admin/outbox")
def outbox(_: User = Depends(require("admin")), db: Session = Depends(get_db)) -> dict:
    rows = db.query(OutboxEmail).order_by(OutboxEmail.created_at.desc()).limit(50).all()
    return {"gmail_configured": gmail_configured(),
            "emails": [{"id": e.id, "to": e.to, "subject": e.subject, "body": e.body, "status": e.status,
                        "error": e.error, "created_at": e.created_at} for e in rows]}


@router.get("/admin/retrain")
def retrain_proposal(_: User = Depends(require("admin")), db: Session = Depends(get_db)) -> dict:
    return retrain.propose(db)


@router.post("/admin/retrain/apply")
def retrain_apply(payload: RetrainApplyIn, _: User = Depends(require("admin")), db: Session = Depends(get_db)) -> dict:
    proposal = retrain.propose(db)
    if proposal["status"] != "ok":
        raise HTTPException(status.HTTP_409_CONFLICT, proposal["message"])
    return retrain.apply(payload.level3_score, payload.frustration_senior)
