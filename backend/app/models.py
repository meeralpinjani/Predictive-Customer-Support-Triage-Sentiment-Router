from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Customer(Base):
    """CRM record: drives customer value and SLA. Customer users link to one."""
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    segment: Mapped[str] = mapped_column(String)  # enterprise | pro | basic | free
    plan: Mapped[str] = mapped_column(String, default="")
    sla_minutes: Mapped[int] = mapped_column(Integer, default=240)
    renewal_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = no renewal (free)
    ltv: Mapped[float] = mapped_column(Float, default=0.0)
    churn_risk: Mapped[float] = mapped_column(Float, default=0.0)
    language: Mapped[str] = mapped_column(String, default="en")


class User(Base):
    """Anyone who signs in: customers, Level 1-3 agents and admins."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)  # None for Google-only accounts
    google_sub: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String, default="customer")  # customer | level1 | level2 | level3 | admin
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    profile_complete: Mapped[bool] = mapped_column(Boolean, default=True)  # False until a Google user picks a plan
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KbArticle(Base):
    __tablename__ = "kb_articles"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    questions: Mapped[str] = mapped_column(Text)  # JSON list string
    answer: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String, default="Help Center")


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    category: Mapped[str] = mapped_column(String, default="howto")
    subject: Mapped[str] = mapped_column(String, default="")
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String, default="web")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String, default="queued")  # queued | in_progress | kb_handled | resolved
    frustration: Mapped[float] = mapped_column(Float, default=0.0)
    urgency: Mapped[float] = mapped_column(Float, default=0.0)
    value: Mapped[float] = mapped_column(Float, default=0.0)
    sla_minutes: Mapped[int] = mapped_column(Integer, default=240)
    intent: Mapped[str] = mapped_column(String, default="other")
    language: Mapped[str] = mapped_column(String, default="en")
    critical_flags: Mapped[str] = mapped_column(String, default="")  # comma separated
    manager_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    priority_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    route: Mapped[str] = mapped_column(String, default="level1")  # level1 | level2 | level3 | auto_kb
    route_reason: Mapped[str] = mapped_column(String, default="")
    route_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation_json: Mapped[str] = mapped_column(Text, default="{}")
    kb_article_id: Mapped[str | None] = mapped_column(String, nullable=True)
    kb_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    kb_action: Mapped[str] = mapped_column(String, default="none")  # none | suggest | auto_reply
    kb_rated: Mapped[bool] = mapped_column(Boolean, default=False)
    analysis_mode: Mapped[str] = mapped_column(String, default="rules")
    analysis_confidence: Mapped[float] = mapped_column(Float, default=0.5)
    assigned_agent_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Message(Base):
    """Conversation on a ticket: customer and agent messages plus system notes."""
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # None = system
    author_role: Mapped[str] = mapped_column(String, default="system")
    kind: Mapped[str] = mapped_column(String, default="message")  # message | system
    body: Mapped[str] = mapped_column(Text)
    frustration: Mapped[float | None] = mapped_column(Float, nullable=True)  # scored customer replies
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CallbackRequest(Base):
    """Level 3 customers can ask an expert to call them back."""
    __tablename__ = "callback_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    phone: Mapped[str] = mapped_column(String)
    preferred_time: Mapped[str] = mapped_column(String, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="requested")  # requested | scheduled | done
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String)  # override | escalate | kb_helpful | kb_not_helpful | resolved
    old_route: Mapped[str | None] = mapped_column(String, nullable=True)
    new_route: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    helpful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
