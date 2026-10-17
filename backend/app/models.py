from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    segment: Mapped[str] = mapped_column(String)  # enterprise | pro | basic | free
    plan: Mapped[str] = mapped_column(String, default="")
    sla_minutes: Mapped[int] = mapped_column(Integer, default=240)
    renewal_days: Mapped[int] = mapped_column(Integer, default=365)


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    level: Mapped[str] = mapped_column(String)  # tier1 | tier2 | senior
    skills: Mapped[str] = mapped_column(String, default="")


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
    subject: Mapped[str] = mapped_column(String, default="")
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String, default="web")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String, default="new")
    frustration: Mapped[float] = mapped_column(Float, default=0.0)
    urgency: Mapped[float] = mapped_column(Float, default=0.0)
    value: Mapped[float] = mapped_column(Float, default=0.0)
    intent: Mapped[str] = mapped_column(String, default="other")
    critical_flags: Mapped[str] = mapped_column(String, default="")  # comma separated
    priority: Mapped[int] = mapped_column(Integer, default=0)
    route: Mapped[str] = mapped_column(String, default="tier1")
    route_reason: Mapped[str] = mapped_column(String, default="")
    route_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation_json: Mapped[str] = mapped_column(Text, default="{}")
    kb_article_id: Mapped[str | None] = mapped_column(String, nullable=True)
    kb_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    kb_action: Mapped[str] = mapped_column(String, default="none")  # none | suggest | auto_reply
    analysis_mode: Mapped[str] = mapped_column(String, default="rules")
    assigned_agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    kind: Mapped[str] = mapped_column(String)  # override | kb_helpful | kb_not_helpful | note | resolved
    old_route: Mapped[str | None] = mapped_column(String, nullable=True)
    new_route: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    helpful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
