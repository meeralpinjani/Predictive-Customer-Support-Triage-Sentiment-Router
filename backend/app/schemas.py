from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class CustomerSummary(BaseModel):
    id: str
    name: str
    segment: str


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    segment: str
    plan: str
    sla_minutes: int
    renewal_days: int


class TicketIn(BaseModel):
    customer_id: str | None = None
    subject: str = Field("", max_length=200)
    body: str = Field(..., min_length=1, max_length=5000)
    channel: str = "web"


class OverrideIn(BaseModel):
    route: Literal["tier1", "tier2", "senior"] | None = None
    priority: int | None = Field(None, ge=0, le=100)
    reason: str = Field(..., min_length=3)


class FeedbackIn(BaseModel):
    kind: Literal["kb_helpful", "kb_not_helpful", "note"]
    note: str = ""


class AnalysisOut(BaseModel):
    frustration: float
    urgency: float
    intent: str
    critical_flags: list[str]
    mode: str


class KbOut(BaseModel):
    action: str
    article_id: str | None = None
    title: str | None = None
    source: str | None = None
    confidence: float = 0.0


class TicketOut(BaseModel):
    id: int
    subject: str
    body: str
    channel: str
    status: str
    created_at: datetime
    wait_minutes: float
    customer: CustomerSummary | None = None
    analysis: AnalysisOut
    priority: int
    components: dict[str, float]
    contributions: dict[str, float]
    route: str
    route_locked: bool
    route_reason: str
    reasons: list[str]
    kb: KbOut
    auto_reply: str | None = None
    assigned_agent_id: int | None = None


class HealthOut(BaseModel):
    status: str
    nlp_mode: str
    kb_size: int
    db: str


class StatsOut(BaseModel):
    total_tickets: int
    counts_by_route: dict[str, int]
    counts_by_status: dict[str, int]
    avg_wait_minutes: float
    p95_wait_minutes: float
    avg_wait_by_segment: dict[str, float]
    override_rate: float
    suggestion_acceptance_rate: float
    abstention_rate: float
