from dataclasses import dataclass, field

from app.config import SLA_RISK_FULL, SLA_RISK_POINTS, SLA_RISK_START, WEIGHTS


@dataclass
class PriorityResult:
    score: int                      # queue order, 0..100 (includes SLA-risk points)
    route_score: int                # used for routing decisions (no SLA-risk points)
    components: dict[str, float]
    contributions: dict[str, float]
    boosts: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


LABEL: dict[str, str] = {
    "urgency": "Time-critical issue",
    "frustration": "High frustration",
    "value": "High-value customer",
    "age": "Waiting close to its reply-by time",
}
BOOST_LABEL: dict[str, str] = {
    "repeat_contact": "Contacted 3+ times this week",
    "renewal_risk": "Renewing soon and unhappy",
    "sla_risk": "Close to its reply-by time",
}


def compute_priority(
    urgency: float,
    frustration: float,
    value: float,
    wait_min: float,
    sla_min: float,
    boosts: dict[str, float] | None = None,
    weights: dict[str, float] | None = None,
) -> PriorityResult:
    """Priority = 100 x (0.30 F + 0.30 U + 0.25 V + 0.15 Age) + rule boosts.

    Age = wait / SLA, capped at 1. From 75% of the SLA a ticket also ramps towards
    +SLA_RISK_POINTS (full at 125%), so it is served before it breaches: nobody starves.
    """
    sla = max(sla_min, 1.0)
    wait = max(wait_min, 0.0)
    comp: dict[str, float] = {
        "urgency": urgency,
        "frustration": frustration,
        "value": value,
        "age": min(wait / sla, 1.0),
    }
    w = weights or WEIGHTS
    contrib = {k: 100.0 * w[k] * v for k, v in comp.items()}

    static = {k: v for k, v in (boosts or {}).items() if v}
    ramp = (wait - SLA_RISK_START * sla) / ((SLA_RISK_FULL - SLA_RISK_START) * sla)
    risk = SLA_RISK_POINTS * min(max(ramp, 0.0), 1.0)
    all_boosts = {**static, **({"sla_risk": risk} if risk > 0 else {})}

    base = sum(contrib.values())
    route_score = int(min(base + sum(static.values()), 100.0) + 0.5)
    score = int(min(base + sum(all_boosts.values()), 100.0) + 0.5)

    # Two strongest reasons: weighted components and rule boosts compete on points.
    pts = {**contrib, **all_boosts}
    top = [k for k in sorted(pts, key=pts.get, reverse=True)[:2] if pts[k] > 0]
    reasons = [
        f"{LABEL[k]} ({round(comp[k] * 100)}%)" if k in LABEL else f"{BOOST_LABEL.get(k, k)} (+{round(pts[k])})"
        for k in top
    ]

    return PriorityResult(
        score=score,
        route_score=route_score,
        components={k: round(v, 4) for k, v in comp.items()},
        contributions={k: round(v, 1) for k, v in contrib.items()},
        boosts={k: round(v, 1) for k, v in all_boosts.items()},
        reasons=reasons,
    )
