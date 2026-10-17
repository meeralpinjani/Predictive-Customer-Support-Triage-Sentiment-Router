"""Real transformer models. Skipped automatically when the models are not installed/cached."""
import pytest

from app.config import settings

pytest.importorskip("transformers")
pytest.importorskip("sentence_transformers")
from app.nlp import hf  # noqa: E402


@pytest.fixture(scope="module")
def models():
    hf.warmup(background=False)
    if not hf.ready():
        pytest.skip(f"HF models unavailable: {hf._state['error'][:120]}")


def test_models_read_tone_and_issue_type(models):
    sig = hf.model_signals("This is the worst app, nothing works and nobody replies!!!")
    assert sig["neg"] > 0.8
    top, p, base = hf.issue_scores("Our production dashboard has been down for an hour")
    assert top == "outage" and base > 0.6


def test_hf_analysis_end_to_end(models, monkeypatch):
    from app.nlp import frustration_model
    from app.nlp.analyzer import analyse
    monkeypatch.setattr(settings, "nlp_mode", "hf")
    monkeypatch.setattr(settings, "hf_timeout_sec", 30.0)
    angry = analyse("Absolutely ridiculous, I'm fed up. Fix it NOW or we cancel!")
    calm = analyse("How do I export my data to CSV? Thanks!")
    assert angry.mode == calm.mode == "hf"
    assert angry.frustration >= frustration_model.threshold("hf") > calm.frustration
    # No rule matches this phrasing; the embedding model still recognises an outage-like issue.
    unseen = analyse("Nothing loads for any of our customers, the whole service is unavailable.")
    assert unseen.urgency >= 0.65
