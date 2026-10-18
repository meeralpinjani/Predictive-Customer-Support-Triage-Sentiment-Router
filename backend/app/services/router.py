from dataclasses import dataclass

from app.categories import CATEGORY_BY_ID
from app.config import settings
from app.nlp import frustration_model
from app.nlp.rules import INTENT_META

LEVEL: dict[str, int] = {"level1": 1, "level2": 2, "level3": 3}
NEXT_LEVEL = {"level1": "level2", "level2": "level3"}

# Problems that need Technical Support (Level 2) whatever category the customer picked.
TECHNICAL_INTENTS = {"bug", "outage", "integration", "performance"}


def frustration_threshold(mode: str | None = None) -> float:
    return frustration_model.threshold(mode or settings.nlp_mode)


@dataclass
class Decision:
    route: str
    reason: str
    kb_action: str  # none | suggest | auto_reply


def higher(a: str, b: str) -> str:
    return a if LEVEL.get(a, 0) >= LEVEL.get(b, 0) else b


def decide(
    score: int,
    frustration: float,
    intent: str,
    flags: list[str],
    kb_conf: float,
    value: float = 0.0,
    confidence: float = 1.0,
    kb_thresholds: tuple[float, float] | None = None,
    allow_auto: bool = True,
    level3_score: int | None = None,
    frustration_senior: float | None = None,
    mode: str | None = None,
    category: str | None = None,
) -> Decision:
    """Routing rules for the three support levels, checked in order.

    Level 3 (Expert Escalation) is reached only by escalation. The customer's category sets
    the starting level (1 or 2); the AI can raise it but never lower it.
    Threshold arguments override the configured values (used by the what-if preview).
    """
    suggest_th, auto_th = kb_thresholds or settings.kb_thresholds()
    level3_score = settings.level3_score if level3_score is None else level3_score
    if frustration_senior is None:
        frustration_senior = settings.frustration_senior
    if frustration_senior is None:
        frustration_senior = frustration_threshold(mode)

    # 1. Critical flags always go to Level 3, whatever the score, plan or category.
    if flags:
        reason = f"Emergency: {', '.join(flags)}"
        if "legal" in flags:
            reason += " · manager notified"
        return Decision("level3", reason, "none")

    # 2. Confident KB answer for a routine, calm, low-priority question.
    routine = INTENT_META.get(intent, {}).get("routine", False)
    if (
        allow_auto
        and kb_conf >= auto_th
        and routine
        and frustration < min(0.4, frustration_senior)
        and score < settings.auto_max_score
        and confidence >= settings.min_auto_confidence
    ):
        return Decision("auto_kb", "Confident knowledge-base match, low risk", "auto_reply")

    kb_action = "suggest" if kb_conf >= suggest_th else "none"

    # 3-5. Escalation to Level 3: frustration, valuable account, very high score.
    if frustration >= frustration_senior:
        return Decision("level3", "High frustration", kb_action)
    if value >= settings.vip_value and score >= settings.vip_score:
        return Decision("level3", "High-value customer", kb_action)
    if score >= level3_score:
        return Decision("level3", "High priority score", kb_action)

    # 6. Technical problems need Level 2, whatever category was picked.
    cat = CATEGORY_BY_ID.get(category or "")
    if intent in TECHNICAL_INTENTS:
        return Decision("level2", "Technical issue detected", kb_action)
    if cat and cat["level"] == "level2":
        return Decision("level2", f"Category: {cat['label']}", kb_action)

    # 7. Everything else: General Support.
    return Decision("level1", f"Category: {cat['label']}" if cat else "General support", kb_action)
