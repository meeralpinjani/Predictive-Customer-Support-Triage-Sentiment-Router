"""Customer value model - playbook Part 8.

value = 0.40*plan + 0.30*ltv + 0.20*churn_risk + 0.10*renewal_soon, each in 0..1.
Churn risk is the CRM figure or recent ticket volume (tickets in 30 days / 5), whichever is higher.
"""
from dataclasses import dataclass

from app.config import LTV_CAP, PLAN_VALUE, UNKNOWN_VALUE, VALUE_WEIGHTS


@dataclass
class ValueResult:
    value: float
    parts: dict[str, float]


def renewal_factor(renewal_days: int | None) -> float:
    if renewal_days is None:
        return 0.0
    return 1.0 if renewal_days <= 30 else 0.5 if renewal_days <= 90 else 0.0


def customer_value(
    segment: str | None,
    ltv: float = 0.0,
    churn_risk: float = 0.0,
    renewal_days: int | None = None,
    recent_tickets: int = 0,
) -> ValueResult:
    if segment is None:
        return ValueResult(UNKNOWN_VALUE, {})
    parts = {
        "plan": PLAN_VALUE.get(segment.lower(), UNKNOWN_VALUE),
        "ltv": min(max(ltv, 0.0) / LTV_CAP, 1.0),
        "churn": min(max(churn_risk, recent_tickets / 5), 1.0),
        "renewal": renewal_factor(renewal_days),
    }
    v = sum(VALUE_WEIGHTS[k] * parts[k] for k in VALUE_WEIGHTS)
    return ValueResult(round(min(v, 1.0), 3), {k: round(p, 3) for k, p in parts.items()})
