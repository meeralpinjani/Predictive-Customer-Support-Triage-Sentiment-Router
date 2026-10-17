import re
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Analysis:
    frustration: float
    urgency: float
    intent: str
    critical_flags: list[str] = field(default_factory=list)
    sentiment: float = 0.0          # -1..1, informational
    confidence: float = 0.5
    mode: str = "rules"

CRITICAL: dict[str, re.Pattern[str]] = {
    "security": re.compile(
        r"\b(hacked|unauthori[sz]ed|breach(ed)?|fraud(ulent)?|stolen|compromised|phishing|identity theft|someone (logged|signed) in|accessed my account|from another country)\b",
        re.I,
    ),
    "legal": re.compile(
        r"\b(lawyer|attorney|legal action|lawsuit|sue you|court|regulator)\b",
        re.I,
    ),
    "safety": re.compile(
        r"\b(injur(y|ed)|smoke|overheat(ing)?|electric shock|unsafe|hazard)\b",
        re.I,
    ),
    "outage": re.compile(
        r"\b(outage|(system|site|service|server|production|dashboard|app|website|platform)\s+(is\s+|has\s+been\s+|was\s+)?down)\b",
        re.I,
    ),
}

NEG_WORDS: list[str] = [
    "worst", "unacceptable", "terrible", "awful", "useless", "ridiculous",
    "furious", "angry", "nobody", "nothing works", "disappointed",
    "frustrated", "fed up", "waste of", "charged twice", "double charge",
]
CHURN_WORDS: list[str] = [
    "cancel", "switch to", "competitor", "chargeback", "never again", "close my account",
]
POS_WORDS: list[str] = [
    "thanks", "thank you", "please", "appreciate", "great",
]
BOOST: dict[str, float] = {
    "asap": 0.10,
    "immediately": 0.10,
    "urgent": 0.10,
    "today": 0.05,
    "deadline": 0.10,
    "losing": 0.10,
    "blocked": 0.10,
}

# (intent, regex, base_urgency, routine, skill) first match wins
INTENTS: list[tuple[str, str, float, bool, str]] = [
    ("billing_dispute", r"charged twice|double charge|duplicate (payment|charge)|wrong charge|refund", 0.60, False, "billing"),
    ("cancellation", r"\bcancel\b|close my account|switch to", 0.50, False, "retention"),
    ("password_reset", r"password|forgot|reset", 0.15, True, "account"),
    ("invoice", r"invoice|receipt|billing history", 0.10, True, "billing"),
    ("how_to", r"\bhow (do|can|to)\b|where (can|do) i", 0.10, True, "general"),
    ("bug", r"\bbug\b|\berror\b|crash|not working|doesn'?t work|nothing works|broken|stopped working", 0.45, False, "technical"),
    ("feature_request", r"would be nice|feature request|please add|suggestion", 0.05, True, "general"),
]

INTENT_META: dict[str, dict[str, Any]] = {i[0]: {"routine": i[3], "skill": i[4]} for i in INTENTS}
INTENT_META.update({
    "security": {"routine": False, "skill": "account"},
    "legal": {"routine": False, "skill": "senior"},
    "safety": {"routine": False, "skill": "senior"},
    "outage": {"routine": False, "skill": "technical"},
    "other": {"routine": False, "skill": "general"},
})


def _count(words: list[str], t: str) -> int:
    return sum(1 for w in words if re.search(rf"\b{re.escape(w)}\b", t))


def critical_flags(text: str) -> list[str]:
    return [k for k, rx in CRITICAL.items() if rx.search(text)]


def detect_intent(text: str, flags: list[str]) -> tuple[str, float]:
    if flags:
        return flags[0], 0.0
    t = text.lower()
    for name, rx, base, _, _ in INTENTS:
        if re.search(rx, t):
            return name, base
    return "other", 0.30


def frustration_rules(text: str) -> float:
    t = text.lower()
    neg = _count(NEG_WORDS, t)
    churn = _count(CHURN_WORDS, t)
    pos = _count(POS_WORDS, t)
    caps = len(re.findall(r"\b[A-Z]{3,}\b", text))
    excl = text.count("!")
    f = (
        0.25 * neg
        + 0.20 * churn
        + 0.10 * min(caps, 3)
        + (0.15 if excl >= 3 else 0.05 if excl >= 1 else 0.0)
        - 0.10 * min(pos, 2)
    )
    return round(max(0.0, min(f, 1.0)), 3)


def urgency_rules(text: str, base: float, flags: list[str]) -> float:
    t = text.lower()
    boost = sum(v for k, v in BOOST.items() if re.search(rf"\b{k}\b", t))
    u = base + boost
    if "security" in flags or "safety" in flags:
        u = max(u, 1.0)
    elif flags:
        u = max(u, 0.90)
    return round(min(u, 1.0), 3)


def analyse_rules(text: str) -> Analysis:
    flags = critical_flags(text)
    intent, base = detect_intent(text, flags)
    fr = frustration_rules(text)
    ur = urgency_rules(text, base, flags)
    return Analysis(
        frustration=fr,
        urgency=ur,
        intent=intent,
        critical_flags=flags,
        sentiment=round(-fr, 3),
        confidence=0.6,
        mode="rules",
    )
