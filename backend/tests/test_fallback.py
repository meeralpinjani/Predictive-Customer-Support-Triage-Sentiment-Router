import time

from app.config import settings
from app.nlp.analyzer import analyse
from app.nlp.kb import TfidfKb, get_kb
import app.nlp.hf as hf_mod
import app.nlp.kb as kb_mod


def _hf_on(monkeypatch):
    monkeypatch.setattr(settings, "nlp_mode", "hf")
    monkeypatch.setitem(hf_mod._state, "status", "ready")


def test_hf_mode_falls_back_on_exception(monkeypatch):
    _hf_on(monkeypatch)

    def broken(text):
        raise RuntimeError("Simulated HF model runtime exception")

    monkeypatch.setattr(hf_mod, "model_signals", broken)
    res = analyse("Our dashboard is down and I am furious!")
    assert res.mode == "rules"
    assert res.intent == "outage"


def test_hf_mode_falls_back_on_timeout(monkeypatch):
    _hf_on(monkeypatch)
    monkeypatch.setattr(settings, "hf_timeout_sec", 0.05)

    def slow(text):
        time.sleep(0.3)
        return {"neg": 0.9, "anger": 0.9}

    monkeypatch.setattr(hf_mod, "model_signals", slow)
    assert analyse("Our dashboard is down!").mode == "rules"


def test_hf_mode_uses_rules_while_models_load(monkeypatch):
    monkeypatch.setattr(settings, "nlp_mode", "hf")
    monkeypatch.setitem(hf_mod._state, "status", "loading")
    assert analyse("How do I reset my password?").mode == "rules"


def test_kb_minilm_fallback_to_tfidf(monkeypatch):
    articles = [{"id": "kb1", "title": "Password Reset", "questions": ["reset password"], "answer": "Click forgot"}]
    original = kb_mod._kb_instance

    class BrokenMiniLm:
        def __init__(self, *args, **kwargs):
            raise ImportError("sentence_transformers unavailable")

    monkeypatch.setattr(kb_mod, "MiniLmKb", BrokenMiniLm)
    try:
        kb = get_kb(articles, mode="hf")
        assert isinstance(kb, TfidfKb)
        assert kb.match("reset password").article_id == "kb1"
    finally:
        kb_mod._kb_instance = original


def test_health_reports_effective_and_requested_mode(client, monkeypatch):
    monkeypatch.setattr(settings, "nlp_mode", "hf")
    monkeypatch.setitem(hf_mod._state, "status", "loading")
    data = client.get("/api/health").json()
    assert data["nlp_requested"] == "hf"
    assert data["nlp_mode"] == "rules"
    assert data["models"] == "loading"
