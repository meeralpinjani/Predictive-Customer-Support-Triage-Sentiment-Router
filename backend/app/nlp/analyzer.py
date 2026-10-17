import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from app.config import settings
from app.nlp import frustration_model
from app.nlp.rules import INTENT_META, Analysis, analyse_rules, urgency_from_base

log = logging.getLogger("triage.nlp")
_pool = ThreadPoolExecutor(max_workers=2)


def _hf_analysis(text: str, base: Analysis) -> Analysis:
    from app.nlp import hf

    model = hf.model_signals(text)
    # Hybrid: the models read tone; the rule lexicons still catch sarcasm cues and Hinglish.
    signals = {
        "neg": max(model["neg"], base.signals["neg"]),          # combined, for display
        "anger": max(model["anger"], base.signals["anger"]),
        "style": base.signals["style"],
        "churn": base.signals["churn"],
        "neg_model": model["neg"],
        "anger_model": model["anger"],
        "neg_rules": base.signals["neg"],
        "anger_rules": base.signals["anger"],
    }
    fr = frustration_model.score(signals, "hf")

    intent, confidence = base.intent, base.confidence
    if base.critical_flags:
        urgency = base.urgency
        confidence = 0.95
    else:
        top, p_top, model_base = hf.issue_scores(text)
        rules_base = INTENT_META[base.intent]["base"]
        if base.intent == "other":
            # No rule matched: trust the model's issue type when it is reasonably sure.
            if p_top >= 0.40:
                intent = top
            mixed = model_base
            confidence = p_top
        else:
            mixed = 0.5 * rules_base + 0.5 * model_base
            confidence = 0.9 if top == base.intent else 0.6
        urgency = urgency_from_base(mixed, text, [])

    return replace(
        base,
        frustration=fr,
        urgency=urgency,
        intent=intent,
        signals=signals,
        sentiment=round(-signals["neg"], 3),
        confidence=round(confidence, 3),
        mode="hf",
    )


def analyse(text: str) -> Analysis:
    base = analyse_rules(text)
    if settings.nlp_mode != "hf":
        return base
    try:
        from app.nlp import hf
        if not hf.ready():
            return base
        return _pool.submit(_hf_analysis, text, base).result(timeout=settings.hf_timeout_sec)
    except Exception as exc:  # timeout, runtime error
        log.warning("HF analysis failed, using rules: %s", exc)
        return base
