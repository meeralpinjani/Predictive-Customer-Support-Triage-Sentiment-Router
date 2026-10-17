from functools import lru_cache
import logging

log = logging.getLogger("triage.hf")


@lru_cache(maxsize=1)
def _pipes():
    from transformers import pipeline
    sent = pipeline("text-classification", model="cardiffnlp/twitter-roberta-base-sentiment-latest", top_k=None)
    emo = pipeline("text-classification", model="j-hartmann/emotion-english-distilroberta-base", top_k=None)
    return sent, emo


def _probs(out):
    if out and isinstance(out[0], list):
        out = out[0]
    return {d["label"].lower(): float(d["score"]) for d in out}


def frustration_hf(text: str, rules_score: float) -> float:
    sent, emo = _pipes()
    s, e = _probs(sent(text[:512])), _probs(emo(text[:512]))
    anger = e.get("anger", 0.0) + e.get("disgust", 0.0) + 0.5 * e.get("sadness", 0.0)
    ml = 0.5 * s.get("negative", 0.0) + 0.5 * min(anger, 1.0)
    return round(min(1.0, 0.6 * ml + 0.4 * rules_score), 3)


def warmup():
    try:
        _pipes()
    except Exception as exc:
        log.warning("HF pipeline warmup warning: %s", exc)
