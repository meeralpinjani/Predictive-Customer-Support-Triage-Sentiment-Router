"""Rule-based NLP: critical flags, intent, urgency and the four frustration signals.

Every function here is deterministic and explainable. In HF mode the transformer models
replace the `neg` and `anger` signals (see app/nlp/hf.py); flags, intent fallback, style,
churn and urgency boosts always come from these rules.
"""
import re
from dataclasses import dataclass, field
from typing import Any

from app.nlp import frustration_model


@dataclass
class Analysis:
    frustration: float
    urgency: float
    intent: str
    critical_flags: list[str] = field(default_factory=list)
    sentiment: float = 0.0          # -1..1, informational
    confidence: float = 0.5         # how sure we are about the intent / signals
    mode: str = "rules"
    language: str = "en"
    signals: dict[str, float] = field(default_factory=dict)   # neg, anger, style, churn
    manager_flag: bool = False


# ---------------------------------------------------------------- critical flags
# Order matters: the first flag found becomes the intent.
CRITICAL: dict[str, re.Pattern[str]] = {
    "legal": re.compile(
        r"\b(lawyers?|attorneys?|legal (action|notice)|lawsuit|sue|suing|court|regulator|ombudsman|consumer forum)\b",
        re.I,
    ),
    "safety": re.compile(
        r"\b(injur(y|ed|ies)|smok(e|ing)|overheat(s|ed|ing)?|electric(al)? shock|unsafe|hazard(ous)?|fire|sparks?|explod(e|ed|ing))\b",
        re.I,
    ),
    "security": re.compile(
        r"\b(hack(ed|er)?|unauthori[sz]ed|breach(ed)?|fraud(ulent)?|stolen|compromised|phishing|identity theft|"
        r"account takeover|suspicious (login|activity|sign-?in)|someone (else )?(logged|signed) (in|into)|"
        r"accessed my account|from another country|without my (permission|consent|knowledge))\b",
        re.I,
    ),
    "outage": re.compile(
        r"\b(outage|(system|site|service|server|servers|production|dashboard|app|website|platform|database|cluster|"
        r"api|portal|network|checkout|everything)\s+(is\s+|are\s+|has\s+been\s+|have\s+been\s+|was\s+|went\s+)?(down|offline|unreachable)|"
        r"site band|band ho gaya)\b",
        re.I,
    ),
}

# Phrases that look critical but are not (checked against the matched span's surroundings).
FALSE_FRIENDS = re.compile(
    r"\b(smoke tests?|smoke testing|sla breach|breach of (contract|sla)|(basketball|tennis|food) court|"
    r"fire (up|off)|fired up|cease ?fire)\b",
    re.I,
)
NEGATORS = {
    "not", "no", "never", "without", "nothing", "isn't", "wasn't", "aren't", "weren't", "don't",
    "doesn't", "didn't", "hasn't", "haven't", "isnt", "wasnt", "dont", "doesnt", "didnt", "nahi", "nahin",
}

LEGAL_MANAGER_FLAG = {"legal"}


def _negated(text: str, start: int) -> bool:
    before = re.findall(r"[a-z']+", text[max(0, start - 40):start].lower())[-4:]
    return any(w in NEGATORS for w in before)


def critical_flags(text: str) -> list[str]:
    masked = FALSE_FRIENDS.sub(lambda m: " " * len(m.group(0)), text)
    flags = []
    for name, rx in CRITICAL.items():
        if any(not _negated(masked, m.start()) for m in rx.finditer(masked)):
            flags.append(name)
    return flags


# ---------------------------------------------------------------- language
HINGLISH = {
    "hai", "hain", "nahi", "nahin", "kya", "mera", "meri", "mere", "mujhe", "karo", "kare", "karein", "ho",
    "gaya", "gayi", "gaye", "chahiye", "kal", "aaj", "jaldi", "bahut", "paisa", "paise", "kyun", "abhi",
    "tak", "raha", "rahi", "kuch", "koi", "yaar", "bhai", "kaise", "kahan", "wapas", "turant", "kab", "hua",
}


def detect_language(text: str) -> str:
    if re.search(r"[ऀ-ॿ]", text):
        return "hi"
    words = re.findall(r"[a-z]+", text.lower())
    return "hi-en" if sum(w in HINGLISH for w in words) >= 2 else "en"


# ---------------------------------------------------------------- intent & urgency
# (intent, regex, base_urgency, routine, skill) - first match wins.
INTENTS: list[tuple[str, str, float, bool, str]] = [
    ("billing_dispute", r"charged twice|double[- ]charge|duplicate (payment|charge)|wrong(ly)? charge|overcharg|refund|"
                        r"billed (after|twice|again)|charged (me )?(after|for|\$)|payment (fail|did not|didn'?t)|"
                        r"paisa (kat|wapas)|paise (kat|wapas)|money (was )?deducted|deducted twice", 0.55, False, "billing"),
    ("access", r"locked out|can'?t (log|sign) ?in|cannot (log|sign) ?in|unable to (log|sign) ?in|"
               r"login (is )?(not working|fails?|failing|broken|error)|account (is )?(locked|disabled|suspended)|"
               r"login nahi", 0.55, False, "account"),
    ("cancellation", r"\bcancel|close my account|switch(ing)? to|terminate (my|our)? ?(subscription|contract|plan)|"
                     r"not renew|won'?t renew|downgrade", 0.45, False, "retention"),
    ("password_reset", r"password|forgot|reset (my|the)? ?(login|account|credentials)|bhool gaya", 0.15, True, "account"),
    ("invoice", r"invoice|receipt|billing history|tax (details|invoice)|\bgst\b|billing address", 0.10, True, "billing"),
    ("bug", r"\bbug\b|\berrors?\b|crash|not working|doesn'?t work|nothing works|broken|stopped working|"
            r"fails? to|glitch|won'?t load|not loading|freez|nahi chal|kaam nahi|nahi ho raha", 0.45, False, "technical"),
    ("performance", r"\b(very |so |really |extremely )?slow\b|slowness|takes (forever|ages|minutes)|\blag(gy|ging)?\b|"
                    r"latency|time[sd]? ?out|loading forever|keeps loading", 0.40, False, "technical"),
    ("complaint", r"nobody (has )?(answered|replied|replies|responds|responded|helped)|no ?(one|body) (has )?(answered|replied|responded)|"
                  r"waiting for (days|weeks|a week|\d+ (days|hours))|terrible service|worst (service|support)|"
                  r"(third|3rd|fourth|fifth) time|how many times|still (no|waiting|not)", 0.35, False, "general"),
    ("how_to", r"\bhow (do|can|to|should|would)\b|where (can|do|is|are)\b|\bkaise\b|\bkahan\b|is it possible|"
               r"\bcan i\b|steps to|\b2fa\b|two[- ]factor|export|change my|update my|how (many|much|long)|"
               r"is there (a|an|any)\b|do you (have|offer|support)|what (is|are) (the|your)", 0.10, True, "general"),
    ("feature_request", r"would be nice|feature request|please add|suggestion|would be great|wish (you|there|it)|"
                        r"could you add|roadmap|it'?d be great", 0.05, True, "general"),
]

CRITICAL_URGENCY = {"security": 1.0, "safety": 1.0, "legal": 0.9, "outage": 0.95}

INTENT_META: dict[str, dict[str, Any]] = {i[0]: {"routine": i[3], "skill": i[4], "base": i[2]} for i in INTENTS}
INTENT_META.update({
    "security": {"routine": False, "skill": "account", "base": 1.0},
    "legal": {"routine": False, "skill": "legal", "base": 0.9},
    "safety": {"routine": False, "skill": "senior", "base": 1.0},
    "outage": {"routine": False, "skill": "technical", "base": 0.95},
    "other": {"routine": False, "skill": "general", "base": 0.30},
})

BOOST: dict[str, float] = {
    r"asap|as soon as possible": 0.15,
    r"immediately|right away|right now": 0.15,
    r"urgent(ly)?|emergency|critical": 0.15,
    r"today|tonight|by eod|end of day": 0.10,
    r"deadline|by tomorrow": 0.15,
    r"production|all (our )?(users|customers|clients)": 0.15,
    r"losing (money|business|customers|revenue|sales)|lost (money|revenue|sales)": 0.20,
    r"blocked|can'?t work|cannot work|stuck": 0.10,
    r"jaldi|turant|abhi": 0.15,
    r"kal tak|aaj hi": 0.10,
}


def detect_intent(text: str, flags: list[str]) -> tuple[str, float, bool]:
    """Returns (intent, base urgency, matched_by_rule)."""
    if flags:
        return flags[0], CRITICAL_URGENCY[flags[0]], True
    t = text.lower()
    for name, rx, base, _, _ in INTENTS:
        if re.search(rx, t):
            return name, base, True
    return "other", INTENT_META["other"]["base"], False


def urgency_boost(text: str) -> float:
    t = text.lower()
    return sum(v for k, v in BOOST.items() if re.search(rf"\b({k})\b", t))


def urgency_from_base(base: float, text: str, flags: list[str]) -> float:
    u = base + urgency_boost(text)
    for f in flags:
        u = max(u, CRITICAL_URGENCY[f])
    return round(min(u, 1.0), 3)


# ---------------------------------------------------------------- frustration signals
NEG_LEX: dict[str, float] = {
    "bad": 0.3, "poor": 0.3, "terrible": 0.5, "awful": 0.5, "horrible": 0.5, "worst": 0.6, "useless": 0.5,
    "disappointed": 0.5, "disappointing": 0.5, "annoying": 0.4, "annoyed": 0.4, "frustrated": 0.6,
    "frustrating": 0.6, "upset": 0.5, "unhappy": 0.5, "unacceptable": 0.6, "ridiculous": 0.5, "pathetic": 0.6,
    "waste": 0.4, "nothing works": 0.5, "not happy": 0.4, "fed up": 0.6, "sick of": 0.6, "nobody": 0.3,
    "no one": 0.3, "still": 0.2, "again": 0.2, "regret": 0.4, "mess": 0.4, "shame": 0.4, "sucks": 0.6,
    "hopeless": 0.5, "incompetent": 0.6, "joke": 0.3, "scam": 0.6, "bakwas": 0.5, "bekaar": 0.5,
    "ghatiya": 0.6, "bura": 0.4, "faltu": 0.5, "pareshan": 0.5,
}
ANGER_LEX: dict[str, float] = {
    "furious": 0.8, "angry": 0.6, "livid": 0.8, "outraged": 0.8, "rage": 0.7, "unacceptable": 0.5,
    "ridiculous": 0.5, "pathetic": 0.5, "disgusting": 0.7, "disgrace": 0.7, "disgraceful": 0.7, "scam": 0.7,
    "is a joke": 0.5, "insane": 0.4, "how many times": 0.6, "third time": 0.5, "fourth time": 0.6,
    "fifth time": 0.7, "for the last time": 0.5, "what the hell": 0.6, "wtf": 0.7, "sick of": 0.5,
    "fed up": 0.5, "worst": 0.4, "useless": 0.4, "incompetent": 0.7, "clowns": 0.6, "bakwas": 0.5,
    "ghatiya": 0.6, "pagal": 0.5, "thanks for nothing": 0.8, "great, just great": 0.7, "oh great": 0.5,
    "love how": 0.5, "yeah right": 0.5, "so much for": 0.5, "bravo": 0.4, "slow clap": 0.6,
    "what a surprise": 0.5, "shocking": 0.4, "absurd": 0.5,
    # common sarcasm markers
    "oh wonderful": 0.6, "just wonderful": 0.6, "thanks a lot": 0.4, "well done": 0.3, "brilliant job": 0.5,
    "outstanding service": 0.5, "world class": 0.4, "never works": 0.5, "as usual": 0.4, "once again": 0.3,
    "seriously?": 0.4, "unbelievable": 0.5, "come on": 0.3, "what a joke": 0.7,
    "bahut badhiya": 0.5, "wah": 0.4, "drama": 0.4, "kya service": 0.5,
}
CHURN_WORDS: list[str] = [
    "cancel", "cancelling", "canceling", "switch to", "switching to", "competitor", "leave you",
    "going to leave", "we will leave", "leaving you", "never again", "chargeback", "report you",
    "close my account", "moving to", "not renewing", "won't renew", "done with you", "last chance",
    "one star", "1 star", "social media", "twitter", "bad review", "public review", "unsubscribe",
]
ACRONYMS = {"API", "SSO", "SAML", "CSV", "PDF", "GST", "VAT", "SLA", "URL", "FAQ", "USB", "HDMI", "IT", "CEO",
            "CTO", "CRM", "UI", "OTP", "EOD", "USD", "INR", "EUR", "SMS", "MFA", "VPN", "AWS", "DNS", "HTTP", "SQL"}


def _lex_score(lex: dict[str, float], t: str) -> float:
    return min(1.0, sum(w for k, w in lex.items() if re.search(rf"(?<![a-z]){re.escape(k)}(?![a-z])", t)))


def style_signal(text: str) -> float:
    words = re.findall(r"\b[A-Z]{3,}\b", text)
    shouted = sum(1 for w in words if w not in ACRONYMS)
    # Acronyms and short tokens (API, IdP, I) are not shouting: leave them out of the caps ratio.
    letters = "".join(w for w in re.findall(r"[A-Za-z]+", text) if len(w) > 3 and w not in ACRONYMS)
    caps_ratio = sum(c.isupper() for c in letters) / max(len(letters), 1)
    # Sentence-initial capitals are normal; only ratios above ~10% read as shouting.
    shout = max(min(shouted / 3, 1.0), min(max(caps_ratio - 0.1, 0.0) / 0.3, 1.0) if len(letters) > 20 else 0.0)
    excl = min(text.count("!"), 5) / 5
    qq = 0.2 if "??" in text else 0.0
    return round(min(1.0, 0.6 * shout + 0.4 * excl + qq), 3)


def churn_signal(text: str) -> float:
    t = text.lower()
    hits = sum(1 for w in CHURN_WORDS if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", t))
    return round(min(1.0, hits / 2), 3)


def rule_signals(text: str) -> dict[str, float]:
    t = text.lower()
    return {
        "neg": round(_lex_score(NEG_LEX, t), 3),
        "anger": round(_lex_score(ANGER_LEX, t), 3),
        "style": style_signal(text),
        "churn": churn_signal(text),
    }


# ---------------------------------------------------------------- analysis
def analyse_rules(text: str) -> Analysis:
    flags = critical_flags(text)
    intent, base, matched = detect_intent(text, flags)
    signals = rule_signals(text)
    fr = frustration_model.score(signals, "rules")
    ur = urgency_from_base(base, text, flags)
    return Analysis(
        frustration=fr,
        urgency=ur,
        intent=intent,
        critical_flags=flags,
        sentiment=round(-signals["neg"], 3),
        confidence=0.75 if matched else 0.4,
        mode="rules",
        language=detect_language(text),
        signals=signals,
        manager_flag=any(f in LEGAL_MANAGER_FLAG for f in flags),
    )
