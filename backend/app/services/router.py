from dataclasses import dataclass

from app.config import settings
from app.nlp import frustration_model
from app.nlp.rules import INTENT_META

LEVEL: dict[str, int] = {"tier1": 1, "tier2": 2, "senior": 3}

# Problems that need a specialist (playbook 10.1: Tier 2 = "specialist matched by skill").
SPECIALIST_INTENTS = {"billing_dispute", "access", "bug", "cancellation"}


def frustration_threshold(mode: str | None = None) -> float:
    return frustration_model.threshold(mode or settings.nlp_mode)


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
    value: float = 0.0,
    confidence: float = 1.0,
    kb_thresholds: tuple[float, float] | None = None,
    allow_auto: bool = True,
    senior_score: int | None = None,
    tier2_score: int | None = None,
    frustration_senior: float | None = None,
    mode: str | None = None,
) -> Decision:
    """Routing ladder (playbook 10.1), checked in order. Threshold arguments override
    the configured values (used by the what-if preview)."""
    suggest_th, auto_th = kb_thresholds or settings.kb_thresholds()
    senior_score = settings.senior_score if senior_score is None else senior_score
    tier2_score = settings.tier2_score if tier2_score is None else tier2_score
    if frustration_senior is None:
        frustration_senior = settings.frustration_senior
    if frustration_senior is None:
        frustration_senior = frustration_threshold(mode)

    # 1. Critical flags always go to Senior, whatever the score or plan.
    if flags:
        reason = f"Critical rule: {', '.join(flags)}"
        if "legal" in flags:
            reason += " · manager notified"
        return Decision("senior", reason, "none")

    # 2. Confident KB answer for a routine, calm, low-priority question.
    routine = INTENT_META.get(intent, {}).get("routine", False)
    if (
        allow_auto
        and kb_conf >= auto_th
        and routine
        and frustration < min(0.4, frustration_senior)
        and score < tier2_score
        and confidence >= settings.min_auto_confidence
    ):
        return Decision("auto_kb", "Confident knowledge-base match, low risk", "auto_reply")

    kb_action = "suggest" if kb_conf >= suggest_th else "none"

    # 3. Highly frustrated customers escalate.
    if frustration >= frustration_senior:
        return Decision("senior", "High frustration", kb_action)

    # 4. Valuable accounts with a meaningful issue escalate.
    if value >= settings.vip_value and score >= settings.vip_score:
        return Decision("senior", "High-value customer", kb_action)

    # 5. Score tiers.
    if score >= senior_score:
        return Decision("senior", "High priority score", kb_action)
    if score >= tier2_score:
        return Decision("tier2", "Moderate priority score", kb_action)
    if intent in SPECIALIST_INTENTS:
        skill = INTENT_META[intent]["skill"]
        article = "an" if skill[0] in "aeiou" else "a"
        return Decision("tier2", f"Needs {article} {skill} specialist", kb_action)
    return Decision("tier1", "Routine request", kb_action)
