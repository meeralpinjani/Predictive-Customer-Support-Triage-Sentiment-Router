from datetime import datetime, timezone
from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime


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
    availability: Mapped[str] = mapped_column(String, default="available")  # agents: available | busy | offline
    max_open: Mapped[int] = mapped_column(Integer, default=8)               # agents: capacity (open tickets)
    recovery_code_hash: Mapped[str | None] = mapped_column(String, nullable=True)  # one-time code shown at sign-up
    reset_requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)  # "ask the admin" requests
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class KbArticle(Base):
    __tablename__ = "kb_articles"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    questions: Mapped[str] = mapped_column(Text)  # JSON list string
    answer: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String, default="Help Center")
    visibility: Mapped[str] = mapped_column(String, default="public")  # public (FAQ + auto-answers) | internal (agent guides)
    tags: Mapped[str] = mapped_column(String, default="")              # internal guides: intents/flags they apply to
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    category: Mapped[str] = mapped_column(String, default="howto")
    subject: Mapped[str] = mapped_column(String, default="")
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String, default="web")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
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
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    first_response_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"), nullable=True)


class Incident(Base):
    """Several tickets about the same underlying problem (e.g. one outage, many reports)."""
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")  # open | resolved
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


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
    # Set by the browser so a retried send returns the saved message instead of a duplicate.
    client_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    __table_args__ = (Index("uq_messages_client_id", "ticket_id", "author_id", "client_message_id", unique=True),)


class CallbackRequest(Base):
    """Level 3 customers can ask an expert to call them back."""
    __tablename__ = "callback_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    phone: Mapped[str] = mapped_column(String)
    preferred_time: Mapped[str] = mapped_column(String, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="requested")  # requested | scheduled | done
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


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
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Attachment(Base):
    """An uploaded screenshot or PDF on a ticket (optionally on one message). Served only to people
    allowed to see the ticket; stored under a random name, never the uploader's filename."""
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), nullable=True, index=True)
    uploader_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String)
    stored_name: Mapped[str] = mapped_column(String, unique=True)
    content_type: Mapped[str] = mapped_column(String)
    size: Mapped[int] = mapped_column(Integer)
    # Kept in the database so files survive hosts whose disk is wiped on restart.
    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AppSetting(Base):
    """Small key/value store for state that must survive redeploys (e.g. accepted router tuning)."""
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class PasswordReset(Base):
    """One-time reset link. Only a hash of the token is stored."""
    __tablename__ = "password_resets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)



class IntegrityAssessment(Base):
    """One integrity review-aid assessment of a ticket (admins only). Append-only: reassessing
    inserts a new row; only a pending row is later filled in with its result."""
    __tablename__ = "integrity_assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    trigger: Mapped[str] = mapped_column(String)                       # ticket_created | customer_reply | attachments | manual
    trigger_key: Mapped[str] = mapped_column(String, unique=True)      # dedupes retries of the same trigger
    status: Mapped[str] = mapped_column(String, default="pending")     # pending | complete | error
    assessment_version: Mapped[str] = mapped_column(String)
    policy_version: Mapped[str] = mapped_column(String)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_status: Mapped[str] = mapped_column(String, default="not_assessed")
    ai_score: Mapped[float | None] = mapped_column(Float, nullable=True)       # mean detector score, not a probability
    ai_score_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    ai_word_count: Mapped[int] = mapped_column(Integer, default=0)
    ai_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    duplicate_max_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    duplicate_method: Mapped[str | None] = mapped_column(String, nullable=True)
    related_ticket_ids: Mapped[str] = mapped_column(Text, default="[]")         # JSON
    consistency_status: Mapped[str] = mapped_column(String, default="insufficient_evidence")
    consistency_findings: Mapped[str] = mapped_column(Text, default="[]")       # JSON
    manipulation_indicators: Mapped[str] = mapped_column(Text, default="[]")    # JSON
    document_findings: Mapped[str] = mapped_column(Text, default="[]")          # JSON
    policy_reasons: Mapped[str] = mapped_column(Text, default="[]")             # JSON
    review_state: Mapped[str] = mapped_column(String, default="clear", index=True)
    review_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class IntegrityReviewAction(Base):
    """Audit trail: every admin review action on an assessment."""
    __tablename__ = "integrity_review_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("integrity_assessments.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String)          # start_review | dismiss | confirm
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class TicketSummary(Base):
    """One revision of a ticket's summary. Append-only: each update inserts revision N+1, so an older
    job can never overwrite a newer summary (unique ticket_id + revision). The current summary is the
    highest revision. The conversation itself stays the source of truth."""
    __tablename__ = "ticket_summaries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="ready")          # ready | stale | pending | failed
    method: Mapped[str] = mapped_column(String, default="extractive")     # extractive | llm | llm_partial | unavailable
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)
    source_key: Mapped[str] = mapped_column(String, default="")           # what the summary was built from
    last_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), nullable=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")              # JSON, see services/summarization.py
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    __table_args__ = (UniqueConstraint("ticket_id", "revision", name="uq_ticket_summary_revision"),)


class Handover(Base):
    """Frozen context snapshot written when a ticket moves to another level or agent. Immutable: there
    is no update path (an ORM guard refuses updates); a correction is a new row that supersedes it."""
    __tablename__ = "handovers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    from_agent_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    from_level: Mapped[str | None] = mapped_column(String, nullable=True)
    to_agent_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    to_level: Mapped[str | None] = mapped_column(String, nullable=True)
    trigger: Mapped[str] = mapped_column(String)          # escalation | reassignment | admin_override | reopen
    reason: Mapped[str] = mapped_column(String(500), default="")
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)   # None = automatic
    source_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot: Mapped[str] = mapped_column(Text, default="{}")             # JSON, frozen at transfer time
    snapshot_method: Mapped[str] = mapped_column(String, default="extractive")   # extractive | llm | fallback_raw
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("handovers.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    __table_args__ = (UniqueConstraint("ticket_id", "sequence", name="uq_handover_sequence"),)
