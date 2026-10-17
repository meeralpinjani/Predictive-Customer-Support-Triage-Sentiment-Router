from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class CustomerSummary(BaseModel):
    id: str
    name: str
    segment: str
    plan: str = ""


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


class TicketIn(BaseModel):
    customer_id: str | None = None
    subject: str = Field("", max_length=200)
    body: str = Field(..., min_length=1, max_length=5000)
    channel: Literal["web", "email", "chat", "api"] = "web"


class OverrideIn(BaseModel):
    route: Literal["tier1", "tier2", "senior"] | None = None
    priority: int | None = Field(None, ge=0, le=100)
    reason: str = Field(..., min_length=3, max_length=500)


class FeedbackIn(BaseModel):
    kind: Literal["kb_helpful", "kb_not_helpful", "note"]
    note: str = Field("", max_length=1000)


class KbTestIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


class WhatIfIn(BaseModel):
    weights: dict[Literal["frustration", "urgency", "value", "age"], float] | None = None
    senior_score: int | None = Field(None, ge=0, le=100)
    tier2_score: int | None = Field(None, ge=0, le=100)
    frustration_senior: float | None = Field(None, ge=0, le=1)


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
    id: int
    subject: str
    body: str
    channel: str
    status: str
    created_at: datetime
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
    route_locked: bool
    route_reason: str
    manager_flag: bool = False
    reasons: list[str]
    kb: KbOut
    auto_reply: str | None = None
    assigned_agent: AgentSummary | None = None


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
