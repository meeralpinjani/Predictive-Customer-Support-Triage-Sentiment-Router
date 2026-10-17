"""Knowledge base and search.

- Customers see public articles only (the Help centre / FAQ).
- Agents and admins also see internal guides; only admins edit.
- Search is scoped by role: customers find FAQ + their own tickets; agents find articles, guides,
  their level's (or assigned) tickets and those tickets' customers; admins find everything.
"""
import json
import re
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import AGENT_ROLES, current_user, require
from app.db import get_db
from app.models import Customer, KbArticle, Ticket, User
from app.nlp.kb import reset_kb
from app.schemas import KbArticleIn
from app.services.knowledge import article_out, search_articles, suggest_for_text, topic_suggestions
from app.categories import level_name

router = APIRouter(prefix="/api", tags=["knowledge"])
STAFF = (*AGENT_ROLES, "admin")


@router.get("/kb-articles")
def list_articles(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    q = db.query(KbArticle)
    if user.role == "customer":
        q = q.filter(KbArticle.visibility == "public")
    return [article_out(a) for a in q.order_by(KbArticle.visibility, KbArticle.title).all()]


@router.get("/kb/suggest")
def suggest(q: str = Query("", max_length=2000), _: User = Depends(current_user),
            db: Session = Depends(get_db)) -> list[dict]:
    """'These articles might help' while typing a new ticket."""
    return suggest_for_text(db, q)


@router.get("/kb/topics")
def topics(_: User = Depends(require("admin")), db: Session = Depends(get_db)) -> dict:
    return topic_suggestions(db)


def _slug(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:30] or "article"
    return f"kb_{base}_{secrets.token_hex(2)}"


def _apply(a: KbArticle, payload: KbArticleIn) -> None:
    a.title = payload.title.strip()
    a.answer = payload.answer.strip()
    a.questions = json.dumps([q.strip() for q in payload.questions if q.strip()])
    a.source = payload.source.strip() or "Help Center"
    a.visibility = payload.visibility
    a.tags = ",".join(t.strip().lower() for t in payload.tags if t.strip())
    a.updated_at = datetime.now(timezone.utc)


@router.post("/kb-articles", status_code=status.HTTP_201_CREATED)
def create_article(payload: KbArticleIn, _: User = Depends(require("admin")), db: Session = Depends(get_db)) -> dict:
    a = KbArticle(id=_slug(payload.title))
    _apply(a, payload)
    db.add(a)
    db.commit()
    reset_kb()  # the auto-answer index rebuilds on next use
    return article_out(a)


@router.patch("/kb-articles/{article_id}")
def update_article(article_id: str, payload: KbArticleIn, _: User = Depends(require("admin")),
                   db: Session = Depends(get_db)) -> dict:
    a = db.get(KbArticle, article_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")
    _apply(a, payload)
    db.commit()
    reset_kb()
    return article_out(a)


@router.delete("/kb-articles/{article_id}")
def delete_article(article_id: str, _: User = Depends(require("admin")), db: Session = Depends(get_db)) -> dict:
    a = db.get(KbArticle, article_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")
    db.delete(a)
    db.commit()
    reset_kb()
    return {"ok": True}


# ---------------------------------------------------------------- search
def _ticket_hit(t: Ticket, db: Session, staff: bool) -> dict:
    cust = db.get(Customer, t.customer_id) if t.customer_id else None
    return {"id": t.id, "subject": t.subject or t.body[:80], "snippet": t.body[:140], "status": t.status,
            "route": t.route, "level_name": level_name(t.route), "customer": cust.name if (cust and staff) else None,
            "url": f"/tickets/{t.id}" if staff else f"/support/tickets/{t.id}"}


@router.get("/search")
def search(q: str = Query(..., min_length=1, max_length=200), user: User = Depends(current_user),
           db: Session = Depends(get_db)) -> dict:
    term = q.strip()
    like = f"%{term}%"
    staff = user.role in STAFF
    out: dict = {"query": term, "articles": search_articles(db, term, include_internal=staff, limit=6)}

    tq = db.query(Ticket)
    if user.role == "customer":
        tq = tq.filter(Ticket.customer_id == user.customer_id)
    elif user.role != "admin":
        tq = tq.filter(or_(Ticket.route == user.role, Ticket.assigned_agent_id == user.id))
    conds = [Ticket.subject.ilike(like), Ticket.body.ilike(like)]
    if term.lstrip("#").isdigit():
        conds.append(Ticket.id == int(term.lstrip("#")))
    if staff:
        conds.append(Ticket.customer_id.in_(db.query(Customer.id).filter(Customer.name.ilike(like))))
    tickets = tq.filter(or_(*conds)).order_by(Ticket.updated_at.desc()).limit(8).all()
    out["tickets"] = [_ticket_hit(t, db, staff) for t in tickets]

    if staff:
        cq = db.query(Customer).filter(Customer.name.ilike(like))
        if user.role != "admin":
            visible = db.query(Ticket.customer_id).filter(
                or_(Ticket.route == user.role, Ticket.assigned_agent_id == user.id))
            cq = cq.filter(Customer.id.in_(visible))
        out["customers"] = [{"id": c.id, "name": c.name, "segment": c.segment, "plan": c.plan,
                             "open_tickets": db.query(Ticket).filter(Ticket.customer_id == c.id,
                                                                      Ticket.status.in_(("queued", "in_progress"))).count()}
                            for c in cq.limit(6).all()]
    if user.role == "admin":
        uq = db.query(User).filter(or_(User.name.ilike(like), User.email.ilike(like))).limit(6).all()
        out["users"] = [{"id": u.id, "name": u.name, "email": u.email, "role": u.role} for u in uq]
    return out
