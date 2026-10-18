from datetime import datetime
from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

Plan = Literal["free", "basic", "pro", "enterprise"]
Availability = Literal["available", "busy", "offline"]


def check_password(p: str) -> str:
    """At least 8 characters with an uppercase letter, a lowercase letter and a number."""
    if len(p) < 8 or not re.search(r"[A-Z]", p) or not re.search(r"[a-z]", p) or not re.search(r"[0-9]", p):
        raise ValueError("Password needs at least 8 characters, an uppercase letter, a lowercase letter and a number")
    return p
Role = Literal["customer", "level1", "level2", "level3", "admin"]


# ---------------------------------------------------------------- accounts
class SignupIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: str = Field(..., min_length=3, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(..., min_length=8, max_length=200)
    plan: Plan = "free"

    _pw = field_validator("password")(check_password)


class LoginIn(BaseModel):
    email: str = Field(..., max_length=200)
    password: str = Field(..., max_length=200)
    remember: bool = False


class ForgotIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)


class RecoverIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    code: str = Field(..., min_length=8, max_length=40)
    password: str = Field(..., max_length=200)

    _pw = field_validator("password")(check_password)


class RecoveryCodeIn(BaseModel):
    current_password: str = Field("", max_length=200)


class ResetIn(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)
    password: str = Field(..., max_length=200)

    _pw = field_validator("password")(check_password)


class AvailabilityIn(BaseModel):
    availability: Availability


class GoogleIn(BaseModel):
    credential: str = Field(..., min_length=10)


class ProfileIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    plan: Plan | None = None


class CustomerSummary(BaseModel):
    id: str
    name: str
    segment: str
    plan: str = ""


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    profile_complete: bool
    auth: Literal["password", "google", "both"]
    customer: CustomerSummary | None = None
    active: bool = True
    created_at: datetime | None = None
    availability: str = "available"
    max_open: int = 8
    has_recovery_code: bool = False
    reset_requested_at: datetime | None = None
    recovery_code: str | None = None   # only right after sign-up / regeneration, never stored in clear


class AdminUserPatch(BaseModel):
    role: Role | None = None
    active: bool | None = None
    plan: Plan | None = None
    availability: Availability | None = None
    max_open: int | None = Field(None, ge=0, le=100)


class KbArticleIn(BaseModel):
    title: str = Field(..., min_length=3, max_length=160)
    answer: str = Field(..., min_length=10, max_length=5000)
    questions: list[str] = Field(default_factory=list, max_length=30)
    source: str = Field("Help Center", max_length=120)
    visibility: Literal["public", "internal"] = "public"
    tags: list[str] = Field(default_factory=list, max_length=12)


class IncidentIn(BaseModel):
    ticket_ids: list[int] = Field(..., min_length=2, max_length=100)
    title: str = Field(..., min_length=3, max_length=160)


class IncidentMessageIn(BaseModel):
    body: str = Field("", max_length=4000)


class RetrainApplyIn(BaseModel):
    level3_score: int = Field(..., ge=30, le=95)
    frustration_senior: float = Field(..., ge=0.2, le=0.95)


class AgentSummary(BaseModel):
    id: int
    name: str
    level: str


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    segment: str
    plan: str
    sla_minutes: int
    renewal_days: int | None
    ltv: float
    churn_risk: float
    language: str


# ---------------------------------------------------------------- tickets
class TicketIn(BaseModel):
    category: str = Field(..., min_length=1, max_length=40)
    subject: str = Field("", max_length=200)
    body: str = Field(..., min_length=1, max_length=5000)
    channel: Literal["web", "email", "chat", "api"] = "web"
    customer_id: str | None = None   # admins only: file a ticket for a CRM customer


class OverrideIn(BaseModel):
    route: Literal["level1", "level2", "level3"] | None = None
    priority: int | None = Field(None, ge=0, le=100)
    reason: str = Field(..., min_length=3, max_length=500)


class EscalateIn(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class FeedbackIn(BaseModel):
    kind: Literal["kb_helpful", "kb_not_helpful"]
    note: str = Field("", max_length=1000)


CLIENT_ID_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"


class MessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(..., min_length=1, max_length=4000)
    # Generated by the browser; a retry with the same id returns the saved message, not a duplicate.
    client_message_id: str | None = Field(None, pattern=CLIENT_ID_PATTERN)


class CallbackIn(BaseModel):
    phone: str = Field(..., min_length=5, max_length=40, pattern=r"^[0-9+()\-\s.]+$")
    preferred_time: str = Field("", max_length=80)
    note: str = Field("", max_length=500)


class CallbackPatch(BaseModel):
    status: Literal["requested", "scheduled", "done"]


class KbTestIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


class WhatIfIn(BaseModel):
    weights: dict[Literal["frustration", "urgency", "value", "age"], float] | None = None
    level3_score: int | None = Field(None, ge=0, le=100)
    frustration_senior: float | None = Field(None, ge=0, le=1)


class AttachmentOut(BaseModel):
    id: int
    filename: str
    content_type: str
    size: int
    url: str
    is_image: bool


class MessageOut(BaseModel):
    id: int
    author_name: str
    author_role: str
    kind: str
    body: str
    created_at: datetime
    frustration: float | None = None
    mine: bool = False
    attachments: list[AttachmentOut] = []


class CallbackOut(BaseModel):
    id: int
    phone: str
    preferred_time: str
    note: str
    status: str
    created_at: datetime


class AnalysisOut(BaseModel):
    frustration: float
    urgency: float
    intent: str
    critical_flags: list[str]
    mode: str
    confidence: float = 0.5
    language: str = "en"
    signals: dict[str, float] = {}


class KbOut(BaseModel):
    action: str
    article_id: str | None = None
    title: str | None = None
    source: str | None = None
    answer: str | None = None
    confidence: float = 0.0
    rated: bool = False


class TicketOut(BaseModel):
    """Full view for agents and admins, including every scoring detail."""
    id: int
    subject: str
    body: str
    category: str
    category_label: str
    channel: str
    status: str
    created_at: datetime
    updated_at: datetime
    wait_minutes: float
    sla_minutes: int
    customer: CustomerSummary | None = None
    analysis: AnalysisOut
    priority: int
    priority_locked: bool = False
    components: dict[str, float]
    contributions: dict[str, float]
    boosts: dict[str, float] = {}
    value_parts: dict[str, float] = {}
    route: str
    level_name: str
    route_locked: bool
    route_reason: str
    manager_flag: bool = False
    reasons: list[str]
    kb: KbOut
    auto_reply: str | None = None
    assigned_agent: AgentSummary | None = None
    message_count: int = 0
    open_callbacks: int = 0
    attachments: list[AttachmentOut] = []
    incident: dict | None = None
    integrity: dict | None = None    # staff only: {"ai_like": bool, "review_suggested": bool}; no scores


class CustomerTicketOut(BaseModel):
    """What a customer sees: no internal scores, just status, answers and the conversation."""
    id: int
    subject: str
    body: str
    category: str
    category_label: str
    status: str
    route: str
    level_name: str
    created_at: datetime
    updated_at: datetime
    agent_name: str | None = None
    auto_reply: str | None = None
    kb: KbOut
    live_chat: bool = False
    attachments: list[AttachmentOut] = []


class HealthOut(BaseModel):
    status: str
    nlp_mode: str
    nlp_requested: str
    models: str
    kb_size: int
    kb_kind: str
    db: str


class StatsOut(BaseModel):
    total_tickets: int
    open_tickets: int
    counts_by_route: dict[str, int]
    counts_by_status: dict[str, int]
    avg_wait_minutes: float
    p95_wait_minutes: float
    avg_wait_by_segment: dict[str, float]
    sla_breached_open: int
    deflection_rate: float
    override_rate: float
    suggestion_acceptance_rate: float
    abstention_rate: float
    kb_ratings: int
    escalations: int
    agents_online: dict[str, int] = {}
