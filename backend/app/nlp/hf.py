"""Pretrained transformer models, run locally.

- cardiffnlp/twitter-roberta-base-sentiment-latest -> negative-sentiment probability
- j-hartmann/emotion-english-distilroberta-base    -> anger + disgust + 0.5 * sadness
- sentence-transformers/all-MiniLM-L6-v2            -> urgency issue type + KB retrieval

Models load once, on a background thread at startup (warmup), so the API answers
immediately with the rules engine until they are ready.
"""
from functools import lru_cache
import logging
import threading

log = logging.getLogger("triage.hf")

SENTIMENT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
EMOTION_MODEL = "j-hartmann/emotion-english-distilroberta-base"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_state = {"status": "idle", "error": ""}   # idle | loading | ready | failed
_lock = threading.Lock()

# Issue types for model-based urgency (embedding approach instead of a
# heavy zero-shot model). Each type has a base urgency and a few prototype sentences.
ISSUES: dict[str, tuple[float, list[str]]] = {
    "outage": (0.95, ["service outage, the system is down", "the website is down for all users",
                      "production servers are offline and nothing loads", "the platform is unavailable"]),
    "security": (1.0, ["account security problem or fraud", "someone hacked my account",
                       "unauthorized access to our admin panel", "suspicious login from an unknown device"]),
    "billing_dispute": (0.55, ["payment or billing error", "I was charged twice", "wrong amount was charged to my card",
                               "I need a refund for an incorrect charge"]),
    "access": (0.55, ["login or access problem", "I am locked out of my account", "cannot sign in to the app"]),
    "bug": (0.45, ["bug, something is not working", "the export feature crashes", "the page shows an error and fails"]),
    "performance": (0.40, ["the app is very slow", "pages take forever to load", "requests keep timing out"]),
    "complaint": (0.35,["complaint about slow or bad support", "nobody has answered my ticket for days",
                         "your support is terrible"]),
    "cancellation": (0.45, ["I want to cancel my subscription", "we are switching to a competitor"]),
    "how_to": (0.10, ["how-to or general question", "how do I change my settings", "where can I find this option"]),
    "password_reset": (0.15, ["how do I reset my password", "I forgot my password"]),
    "invoice": (0.10, ["where can I download my invoices", "I need a receipt for my payment"]),
    "feature_request": (0.05, ["feature request or feedback", "it would be nice to have dark mode",
                               "please add an integration"]),
}


def status() -> str:
    return _state["status"]


def ready() -> bool:
    return _state["status"] == "ready"


@lru_cache(maxsize=1)
def _pipes():
    from transformers import pipeline
    sent = pipeline("text-classification", model=SENTIMENT_MODEL, top_k=None)
    emo = pipeline("text-classification", model=EMOTION_MODEL, top_k=None)
    return sent, emo


@lru_cache(maxsize=1)
def embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBED_MODEL)


@lru_cache(maxsize=1)
def _issue_index():
    labels, owners = [], []
    for name, (_, protos) in ISSUES.items():
        labels.extend(protos)
        owners.extend([name] * len(protos))
    vecs = embedder().encode(labels, convert_to_tensor=True, normalize_embeddings=True)
    return vecs, owners


def _load() -> None:
    try:
        _pipes()
        _issue_index()
        _state["status"] = "ready"
        log.info("HF models ready")
    except Exception as exc:  # missing packages, no cache and no network, ...
        _state.update(status="failed", error=str(exc))
        log.warning("HF models unavailable, staying on rules: %s", exc)


def warmup(background: bool = True) -> None:
    with _lock:
        if _state["status"] in ("loading", "ready"):
            return
        _state["status"] = "loading"
    if background:
        threading.Thread(target=_load, name="hf-warmup", daemon=True).start()
    else:
        _load()


def _probs(out):
    if out and isinstance(out[0], list):
        out = out[0]
    return {d["label"].lower(): float(d["score"]) for d in out}


def model_signals(text: str) -> dict[str, float]:
    """neg and anger signals from the transformer models."""
    sent, emo = _pipes()
    s, e = _probs(sent(text[:512])), _probs(emo(text[:512]))
    anger = e.get("anger", 0.0) + e.get("disgust", 0.0) + 0.5 * e.get("sadness", 0.0)
    return {"neg": round(s.get("negative", 0.0), 3), "anger": round(min(anger, 1.0), 3)}


def issue_scores(text: str) -> tuple[str, float, float]:
    """Returns (top issue, its probability, model base urgency)."""
    import torch
    from sentence_transformers import util

    vecs, owners = _issue_index()
    q = embedder().encode(text[:512], convert_to_tensor=True, normalize_embeddings=True)
    sims = util.cos_sim(q, vecs)[0]
    best: dict[str, float] = {}
    for owner, sim in zip(owners, sims.tolist()):
        best[owner] = max(best.get(owner, -1.0), sim)
    names = list(best)
    probs = torch.softmax(torch.tensor([best[n] for n in names]) / 0.05, dim=0).tolist()
    dist = dict(zip(names, probs))
    top = max(dist, key=dist.get)
    weighted = sum(ISSUES[n][0] * p for n, p in dist.items())
    base = 0.5 * weighted + 0.5 * ISSUES[top][0] * dist[top]
    return top, round(dist[top], 3), round(base, 3)
