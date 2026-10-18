"""Turns the four frustration signals into one score in 0..1.

Default (only if the fitted weights are missing): 0.35*neg + 0.30*anger + 0.15*style + 0.20*churn.
If eval/train_frustration.py has been run, a logistic regression fitted on the training
split replaces it.
The fitted coefficients live in frustration_weights.json, one set per NLP mode, so the
score stays a transparent weighted sum passed through a sigmoid.
"""
import json
import math
from functools import lru_cache
from pathlib import Path

SIGNALS = ("neg", "anger", "style", "churn")
# In HF mode the regression sees model and rule signals separately, so it can learn that the
# emotion model over-reads anger in calm problem reports while rule cues catch sarcasm.
HF_SIGNALS = ("neg_model", "anger_model", "neg_rules", "anger_rules", "style", "churn")


DEFAULT_BLEND = {"neg": 0.35, "anger": 0.30, "style": 0.15, "churn": 0.20}
WEIGHTS_PATH = Path(__file__).with_name("frustration_weights.json")


def features(mode: str) -> tuple[str, ...]:
    return HF_SIGNALS if mode == "hf" else SIGNALS


@lru_cache(maxsize=1)
def _fitted() -> dict:
    try:
        return json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def reload() -> None:
    _fitted.cache_clear()


def describe(mode: str) -> dict:
    fit = _fitted().get(mode)
    if fit:
        return {"kind": "logistic", **fit}
    return {"kind": "default_linear", "coef": DEFAULT_BLEND, "intercept": 0.0}


def threshold(mode: str, default: float = 0.70) -> float:
    """"High frustration" cut-off chosen by cross-validation on the training split."""
    return float(_fitted().get(mode, {}).get("threshold", default))


def score(signals: dict[str, float], mode: str) -> float:
    fit = _fitted().get(mode)
    if not fit:
        return round(min(1.0, sum(DEFAULT_BLEND[k] * signals.get(k, 0.0) for k in SIGNALS)), 3)
    z = fit["intercept"] + sum(c * signals.get(k, 0.0) for k, c in fit["coef"].items())
    return round(1.0 / (1.0 + math.exp(-z)), 3)
