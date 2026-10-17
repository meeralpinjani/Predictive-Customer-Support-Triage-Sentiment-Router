from dataclasses import dataclass
from app.config import WEIGHTS

@dataclass
class PriorityResult:
    score: int
    components: dict[str, float]
    contributions: dict[str, float]
    reasons: list[str]

LABEL: dict[str, str] = {
    "urgency": "Time-critical issue",
    "frustration": "High frustration",
    "value": "Important account segment",
    "age": "Waiting close to SLA",
}


def compute_priority(
    urgency: float,
    frustration: float,
    value: float,
    wait_min: float,
    sla_min: float,
) -> PriorityResult:
    age = min(max(wait_min, 0.0) / max(sla_min, 1.0), 1.0)
    comp: dict[str, float] = {
        "urgency": urgency,
        "frustration": frustration,
        "value": value,
        "age": age,
    }
    contrib: dict[str, float] = {k: 100.0 * WEIGHTS[k] * v for k, v in comp.items()}
    score = int(sum(contrib.values()) + 0.5)  # round half up

    top = sorted(contrib, key=contrib.get, reverse=True)[:2]
    reasons = [f"{LABEL[k]} ({round(comp[k] * 100)}%)" for k in top if contrib[k] > 0]

    return PriorityResult(
        score=score,
        components={k: round(v, 4) for k, v in comp.items()},
        contributions={k: round(v, 1) for k, v in contrib.items()},
        reasons=reasons,
    )
