"""Classifier metrics on the held-out TEST split (playbook 13.1-13.2).

    python -m eval.evaluate_nlp
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, f1_score, precision_recall_fscore_support

from app.config import settings
from app.nlp import frustration_model
from app.nlp.rules import INTENT_META
from app.services.priority import compute_priority
from app.services.router import decide
from eval.common import analyse_all, kb_for, labelled

ROUTINE_INTENTS = {"password_reset", "invoice", "how_to", "feature_request"}
MID_VALUE = 0.35          # a typical basic/pro customer, so escalation reflects the text alone


def to_level(u: float) -> str:
    return "high" if u >= 0.65 else "medium" if u >= 0.35 else "low"


def _prf(y_true, y_pred) -> dict:
    p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    return {"precision": round(float(p), 3), "recall": round(float(r), 3), "f1": round(float(f), 3)}


def evaluate(mode: str, split: str = "test") -> dict:
    df = labelled(split)
    analyses, ms = analyse_all(df["text"].tolist(), mode)
    # Same cut-off the router uses for "High frustration" escalation (fitted on train only).
    FRUSTRATED_AT = frustration_model.threshold(analyses[0].mode if analyses else mode)
    kb = kb_for(mode)
    thresholds = settings.kb_thresholds(mode)

    df["pred_urgency"] = [to_level(a.urgency) for a in analyses]
    df["pred_frustration"] = [a.frustration for a in analyses]
    df["pred_intent"] = [a.intent for a in analyses]
    df["pred_critical"] = [int(bool(a.critical_flags)) for a in analyses]

    routes = []
    for text, a in zip(df["text"], analyses):
        kb_conf = kb.match(text).confidence
        pr = compute_priority(a.urgency, a.frustration, MID_VALUE, 0, 240)
        d = decide(pr.route_score, a.frustration, a.intent, a.critical_flags, kb_conf,
                   value=MID_VALUE, confidence=a.confidence, kb_thresholds=thresholds, mode=a.mode)
        routes.append(d.route)
    df["pred_route"] = routes

    true_urgent = (df["urgency_label"] == "high") | (df["critical"] == 1)
    true_frustrated = df["frustration_label"] == "high"
    should_escalate = true_urgent | true_frustrated
    sent_senior = df["pred_route"] == "senior"
    auto = df["pred_route"] == "auto_kb"
    safe_auto = df["intent"].isin(ROUTINE_INTENTS) & (df["frustration_label"] != "high")

    report = classification_report(df["urgency_label"], df["pred_urgency"], labels=["high", "medium", "low"],
                                   output_dict=True, zero_division=0)
    res = {
        "mode": analyses[0].mode if analyses else mode,
        "split": split,
        "n": int(len(df)),
        "urgency": {
            "macro_f1": round(float(f1_score(df["urgency_label"], df["pred_urgency"], average="macro")), 3),
            "accuracy": round(float((df["urgency_label"] == df["pred_urgency"]).mean()), 3),
            "per_class": {k: {m: round(float(v[m]), 3) for m in ("precision", "recall", "f1-score")}
                          for k, v in report.items() if k in ("high", "medium", "low")},
            "urgent_binary": _prf(true_urgent, df["pred_urgency"] == "high"),
        },
        "critical": _prf(df["critical"] == 1, df["pred_critical"] == 1),
        "frustration": {**_prf(true_frustrated, df["pred_frustration"] >= FRUSTRATED_AT), "threshold": FRUSTRATED_AT},
        "intent_accuracy": round(float((df["intent"] == df["pred_intent"]).mean()), 3),
        "escalation": {
            "precision": round(float(should_escalate[sent_senior].mean()), 3) if sent_senior.any() else 0.0,
            "recall": round(float(sent_senior[should_escalate].mean()), 3) if should_escalate.any() else 0.0,
            "sent_to_senior": int(sent_senior.sum()),
        },
        "auto_answer": {
            "count": int(auto.sum()),
            "safe_precision": round(float(safe_auto[auto].mean()), 3) if auto.any() else 0.0,
            "deflection_rate": round(float(auto.mean()), 3),
            "routine_coverage": round(float(auto[safe_auto].mean()), 3) if safe_auto.any() else 0.0,
        },
        "hinglish": {
            "n": int((df["language"] == "hi-en").sum()),
            "urgency_accuracy": round(float((df.loc[df["language"] == "hi-en", "urgency_label"]
                                             == df.loc[df["language"] == "hi-en", "pred_urgency"]).mean()), 3)
            if (df["language"] == "hi-en").any() else None,
        },
        "latency_ms": {"mean": round(float(np.mean(ms)), 1), "p95": round(float(np.percentile(ms, 95)), 1)},
    }

    mistakes = df[(df["urgency_label"] != df["pred_urgency"]) | (true_frustrated != (df["pred_frustration"] >= FRUSTRATED_AT))]
    mistakes.to_csv(Path(__file__).resolve().parent / f"nlp_mistakes_{mode}.csv", index=False)
    return res


if __name__ == "__main__":
    import json
    for mode in ("rules", "hf"):
        print(json.dumps(evaluate(mode), indent=2))
