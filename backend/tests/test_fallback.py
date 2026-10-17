import time
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.nlp.analyzer import analyse
from app.nlp.kb import TfidfKb, get_kb

client = TestClient(app)


def test_hf_mode_fallback_on_exception(monkeypatch):
    # Enable HF mode
    monkeypatch.setattr(settings, "nlp_mode", "hf")

    # Mock hf.frustration_hf to raise an unexpected runtime error (e.g. CUDA OOM or network error)
    def broken_frustration(text, base_score):
        raise RuntimeError("Simulated HF model runtime exception")

    import app.nlp.hf as hf_mod
    monkeypatch.setattr(hf_mod, "frustration_hf", broken_frustration)

    # Analyse text - must gracefully fall back to rules without throwing 500
    res = analyse("Our dashboard is down and I am furious!")
    assert res is not None
    assert res.mode == "rules"
    assert res.intent in ("outage", "bug")


def test_hf_mode_fallback_on_timeout(monkeypatch):
    # Enable HF mode with a tiny timeout
    monkeypatch.setattr(settings, "nlp_mode", "hf")
    monkeypatch.setattr(settings, "hf_timeout_sec", 0.05)

    def slow_frustration(text, base_score):
        time.sleep(0.3)
        return 0.99

    import app.nlp.hf as hf_mod
    monkeypatch.setattr(hf_mod, "frustration_hf", slow_frustration)

    # Must time out and return rules baseline
    res = analyse("Our dashboard is down!")
    assert res.mode == "rules"


def test_kb_minilm_fallback_to_tfidf(monkeypatch):
    # Mock MiniLmKb to fail on init
    articles = [
        {"id": "kb1", "title": "Password Reset", "questions": ["reset password"], "answer": "Click forgot password"}
    ]

    import app.nlp.kb as kb_mod
    orig_kb = kb_mod._kb_instance

    class BrokenMiniLm:
        def __init__(self, *args, **kwargs):
            raise ImportError("sentence_transformers unavailable")

    monkeypatch.setattr(kb_mod, "MiniLmKb", BrokenMiniLm)

    try:
        # get_kb in hf mode should catch error and fall back to TfidfKb
        kb = get_kb(articles, mode="hf")
        assert isinstance(kb, TfidfKb)
        match = kb.match("reset password")
        assert match.article_id == "kb1"
    finally:
        kb_mod._kb_instance = orig_kb


def test_health_shows_active_nlp_mode(monkeypatch):
    # Check default rules mode
    monkeypatch.setattr(settings, "nlp_mode", "rules")
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["nlp_mode"] == "rules"

    # Check hf mode
    monkeypatch.setattr(settings, "nlp_mode", "hf")
    res_hf = client.get("/api/health")
    assert res_hf.status_code == 200
    assert res_hf.json()["nlp_mode"] == "hf"
