from dataclasses import dataclass
from app.config import settings
from app.nlp.rules import INTENT_META

LEVEL: dict[str, int] = {"tier1": 1, "tier2": 2, "senior": 3}

@dataclass
class Decision:
    route: str
    reason: str
    kb_action: str  # none | suggest | auto_reply


def decide(
    score: int,
    frustration: float,
    intent: str,
    flags: list[str],
    kb_conf: float,
) -> Decision:
    # 1. Critical flags (safety first) always route to Senior
    if flags:
        return Decision("senior", f"Critical rule: {', '.join(flags)}", "none")

    # 2. Extreme customer frustration
    if frustration >= settings.frustration_senior:
        return Decision("senior", "High frustration", "none")

    # 3. Automated self-service KB resolution
    routine = INTENT_META.get(intent, {}).get("routine", False)
    if (
        kb_conf >= settings.kb_auto_threshold
        and routine
        and frustration < 0.4
        and score < settings.tier2_score
    ):
        return Decision("auto_kb", "Confident knowledge-base match, low risk", "auto_reply")

    # 4. Standard score-based tiers
    if score >= settings.senior_score:
        route, reason = "senior", "High priority score"
    elif score >= settings.tier2_score:
        route, reason = "tier2", "Moderate priority score"
    else:
        route, reason = "tier1", "Routine request"

    # 5. KB Suggestion gating for human tiers
    kb_action = "suggest" if kb_conf >= settings.kb_suggest_threshold else "none"
    return Decision(route, reason, kb_action)
