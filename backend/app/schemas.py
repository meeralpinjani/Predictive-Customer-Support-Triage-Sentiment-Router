from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Plan = Literal["free", "basic", "pro", "enterprise"]
Role = Literal["customer", "level1", "level2", "level3", "admin"]


# ---------------------------------------------------------------- accounts
class SignupIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: str = Field(..., min_length=3, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(..., min_length=8, max_length=200)
    plan: Plan = "free"


class LoginIn(BaseModel):
    email: str = Field(..., max_length=200)
    password: str = Field(..., max_length=200)


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


class AdminUserPatch(BaseModel):
    role: Role | None = None
    active: bool | None = None
    plan: Plan | None = None


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


class MessageIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


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


class MessageOut(BaseModel):
    id: int
    author_name: str
    author_role: str
    kind: str
    body: str
    created_at: datetime
    frustration: float | None = None
    mine: bool = False


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
