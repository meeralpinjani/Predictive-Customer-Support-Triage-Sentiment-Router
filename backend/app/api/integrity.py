"""Integrity review aid API. Admins only: every endpoint returns 403 to customers and agents.

Nothing here changes a ticket. Review actions change only an assessment's review state and are
audited (integrity_review_actions + a log line without customer text).
"""
from datetime import date, datetime, time, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import check_rate_limit, require
from app.db import get_db
from app.models import IntegrityAssessment, IntegrityReviewAction, Ticket, User
from app.services import integrity
from app.services.integrity import load
from app.services.triage import OPEN, wait_minutes

router = APIRouter(prefix="/api/integrity", tags=["integrity"])
admin_only = require("admin")
MAX_BODY_BYTES = 4096

ReviewState = Literal["clear", "review_recommended", "under_review", "confirmed_integrity_concern", "dismissed"]
AiStatus = Literal["not_assessed", "insufficient_text", "unsupported_language", "model_unavailable", "assessed"]


def small_body(request: Request) -> None:
    length = request.headers.get("content-length")
    if length is not None and (not length.isdigit() or int(length) > MAX_BODY_BYTES):
        raise HTTPException(413, "Request body too large")


# ---------------------------------------------------------------- schemas
class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["start_review", "dismiss", "confirm"]
    reason: str = Field("", max_length=1000)

    @model_validator(mode="after")
    def reason_required(self):
        self.reason = self.reason.strip()
        if self.action == "confirm" and len(self.reason) < 10:
            raise ValueError("A reason of at least 10 characters is required to confirm a concern")
        return self


class TicketSummary(BaseModel):
    id: int
    subject: str
    category: str
    priority: int
    route: str
    critical_flags: list[str]
    sla_status: str           # ok | near | late | closed
    status: str


class AssessmentOut(BaseModel):
    id: int
    ticket_id: int
    trigger: str
    status: str
    review_state: str
    review_recommended: bool
    ai_status: str
    ai_score: float | None = Field(None, description="Detector score (not a probability)")
    duplicate_count: int
    created_at: datetime
    updated_at: datetime
    ticket: TicketSummary | None = None


class AssessmentDetail(AssessmentOut):
    assessment_version: str
    policy_version: str
    model_name: str | None
    model_version: str | None
    ai_score_max: float | None
    ai_chunk_count: int
    ai_word_count: int
    ai_reason: str | None
    ai_limitations: list[str]
    duplicate_max_similarity: float | None
    duplicate_method: str | None
    related: list[dict]
    consistency_status: str
    consistency_findings: list[dict]
    manipulation_indicators: list[dict]
    document_findings: list[dict]
    policy_reasons: list[str]
    error: str | None


class AssessmentPage(BaseModel):
    items: list[AssessmentOut]
    total: int
    page: int
    page_size: int
    stats: dict


class ActionOut(BaseModel):
    id: int
    assessment_id: int
    actor_id: int
    actor_name: str
    action: str
    reason: str
    created_at: datetime


# ---------------------------------------------------------------- helpers
def _sla_status(t: Ticket) -> str:
    if t.status not in OPEN:
        return "closed"
    ratio = wait_minutes(t.created_at, datetime.now(timezone.utc)) / max(t.sla_minutes or 240, 1)
    return "late" if ratio >= 1 else "near" if ratio >= 0.75 else "ok"


def _ticket(t: Ticket | None) -> TicketSummary | None:
    if t is None:
        return None
    return TicketSummary(id=t.id, subject=t.subject or "", category=t.category, priority=t.priority, route=t.route,
                         critical_flags=[f for f in (t.critical_flags or "").split(",") if f],
                         sla_status=_sla_status(t), status=t.status)


def _out(a: IntegrityAssessment, t: Ticket | None) -> AssessmentOut:
    return AssessmentOut(id=a.id, ticket_id=a.ticket_id, trigger=a.trigger, status=a.status, review_state=a.review_state,
                         review_recommended=a.review_recommended, ai_status=a.ai_status, ai_score=a.ai_score,
                         duplicate_count=len(load(a.related_ticket_ids)), created_at=a.created_at,
                         updated_at=a.updated_at, ticket=_ticket(t))


def _get(db: Session, assessment_id: int) -> IntegrityAssessment:
    a = db.get(IntegrityAssessment, assessment_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found")
    return a


def _latest_ids(db: Session):
    return db.query(func.max(IntegrityAssessment.id)).group_by(IntegrityAssessment.ticket_id)


# ---------------------------------------------------------------- endpoints
@router.get("/assessments", response_model=AssessmentPage)
def list_assessments(
    review_state: ReviewState | None = None,
    ai_status: AiStatus | None = None,
    has_duplicates: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = Query(None, max_length=100, description="Search ticket subject or id"),
    sort: Literal["newest", "oldest", "priority"] = "newest",
    page: int = Query(1, ge=1, le=10_000),
    page_size: int = Query(25, ge=1, le=100),
    _: User = Depends(admin_only),
    db: Session = Depends(get_db),
) -> AssessmentPage:
    """Latest assessment per ticket."""
    base = (db.query(IntegrityAssessment, Ticket).join(Ticket, Ticket.id == IntegrityAssessment.ticket_id)
            .filter(IntegrityAssessment.id.in_(_latest_ids(db))))
    stats_rows = base.with_entities(IntegrityAssessment.review_state, IntegrityAssessment.ai_status).all()
    stats = {"total": len(stats_rows),
             "by_review_state": {s: sum(1 for r, _ in stats_rows if r == s) for s in integrity.REVIEW_STATES},
             "by_ai_status": {}}
    for _, s in stats_rows:
        stats["by_ai_status"][s] = stats["by_ai_status"].get(s, 0) + 1
    qry = base
    if review_state:
        qry = qry.filter(IntegrityAssessment.review_state == review_state)
    if ai_status:
        qry = qry.filter(IntegrityAssessment.ai_status == ai_status)
    if has_duplicates is not None:
        qry = qry.filter((IntegrityAssessment.related_ticket_ids != "[]") if has_duplicates
                         else (IntegrityAssessment.related_ticket_ids == "[]"))
    if date_from:
        qry = qry.filter(IntegrityAssessment.created_at >= datetime.combine(date_from, time.min, timezone.utc))
    if date_to:
        qry = qry.filter(IntegrityAssessment.created_at <= datetime.combine(date_to, time.max, timezone.utc))
    if q:
        term = q.strip()
        cond = Ticket.subject.ilike(f"%{term}%")
        if term.lstrip("#").isdigit():
            cond = cond | (Ticket.id == int(term.lstrip("#")))
        qry = qry.filter(cond)
    order = {"newest": IntegrityAssessment.id.desc(), "oldest": IntegrityAssessment.id.asc(),
             "priority": Ticket.priority.desc()}[sort]
    total = qry.count()
    rows = qry.order_by(order).offset((page - 1) * page_size).limit(page_size).all()
    return AssessmentPage(items=[_out(a, t) for a, t in rows], total=total, page=page, page_size=page_size, stats=stats)


@router.get("/assessments/{assessment_id}", response_model=AssessmentDetail)
def get_assessment(assessment_id: int, _: User = Depends(admin_only), db: Session = Depends(get_db)) -> AssessmentDetail:
    from app.nlp.ai_authorship import LIMITATIONS
    a = _get(db, assessment_id)
    base = _out(a, db.get(Ticket, a.ticket_id)).model_dump()
    return AssessmentDetail(
        **base, assessment_version=a.assessment_version, policy_version=a.policy_version, model_name=a.model_name,
        model_version=a.model_version, ai_score_max=a.ai_score_max, ai_chunk_count=a.ai_chunk_count,
        ai_word_count=a.ai_word_count, ai_reason=a.ai_reason, ai_limitations=LIMITATIONS,
        duplicate_max_similarity=a.duplicate_max_similarity, duplicate_method=a.duplicate_method,
        related=load(a.related_ticket_ids), consistency_status=a.consistency_status,
        consistency_findings=load(a.consistency_findings), manipulation_indicators=load(a.manipulation_indicators),
        document_findings=load(a.document_findings), policy_reasons=load(a.policy_reasons), error=a.error,
    )


@router.get("/assessments/{assessment_id}/related")
def related_tickets(assessment_id: int, user: User = Depends(admin_only), db: Session = Depends(get_db)) -> list[dict]:
    """Related tickets with short excerpts, only for tickets this admin may see."""
    from app.api.tickets import can_view
    a = _get(db, assessment_id)
    out = []
    for r in load(a.related_ticket_ids):
        t = db.get(Ticket, r.get("ticket_id"))
        if t is None or not can_view(user, t):
            continue
        out.append({**r, "subject": t.subject or "", "excerpt": (t.body or "")[:160], "route": t.route,
                    "status": t.status, "customer_id": t.customer_id})
    return out


@router.post("/assessments/{assessment_id}/review", response_model=ActionOut, dependencies=[Depends(small_body)])
def review_assessment(assessment_id: int, payload: ReviewIn, user: User = Depends(admin_only),
                      db: Session = Depends(get_db)) -> ActionOut:
    a = _get(db, assessment_id)
    if a.status != "complete":
        raise HTTPException(status.HTTP_409_CONFLICT, "This assessment hasn't finished yet")
    act = integrity.review(db, a, user, payload.action, payload.reason)
    return ActionOut(id=act.id, assessment_id=a.id, actor_id=user.id, actor_name=user.name, action=act.action,
                     reason=act.reason, created_at=act.created_at)


@router.get("/assessments/{assessment_id}/history", response_model=list[ActionOut])
def review_history(assessment_id: int, _: User = Depends(admin_only), db: Session = Depends(get_db)) -> list[ActionOut]:
    """Review actions on every assessment of this ticket, newest first."""
    a = _get(db, assessment_id)
    ids = [x for (x,) in db.query(IntegrityAssessment.id).filter(IntegrityAssessment.ticket_id == a.ticket_id).all()]
    rows = (db.query(IntegrityReviewAction, User).join(User, User.id == IntegrityReviewAction.actor_id)
            .filter(IntegrityReviewAction.assessment_id.in_(ids)).order_by(IntegrityReviewAction.id.desc()).all())
    return [ActionOut(id=r.id, assessment_id=r.assessment_id, actor_id=r.actor_id, actor_name=u.name, action=r.action,
                      reason=r.reason, created_at=r.created_at) for r, u in rows]


@router.get("/tickets/{ticket_id}/assessments", response_model=list[AssessmentOut])
def ticket_assessments(ticket_id: int, _: User = Depends(admin_only), db: Session = Depends(get_db)) -> list[AssessmentOut]:
    t = db.get(Ticket, ticket_id)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    rows = db.query(IntegrityAssessment).filter(IntegrityAssessment.ticket_id == ticket_id).order_by(IntegrityAssessment.id.desc()).all()
    return [_out(a, t) for a in rows]


@router.post("/tickets/{ticket_id}/reassess", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(small_body)])
def reassess(ticket_id: int, _: User = Depends(admin_only), db: Session = Depends(get_db)) -> dict:
    from app.config import settings
    if not settings.ai_integrity_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "The integrity analyzer is turned off (AI_INTEGRITY_ENABLED)")
    if db.get(Ticket, ticket_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    check_rate_limit(f"integrity-reassess:{ticket_id}", limit=settings.ai_integrity_reassess_per_hour, window_sec=3600)
    aid = integrity.schedule(ticket_id, "manual", integrity.manual_key())
    if aid is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not schedule the assessment")
    return {"assessment_id": aid, "status": "pending"}


@router.get("/status")
def integrity_status(_: User = Depends(admin_only)) -> dict:
    from app.config import settings
    from app.nlp.ai_authorship import MODEL_NAME, startup_check
    return {"enabled": settings.ai_integrity_enabled, "model_name": MODEL_NAME,
            "model_check": startup_check(), "policy_version": integrity.POLICY_VERSION,
            "review_threshold": settings.ai_integrity_review_threshold, "provisional": True}
