import json
from pathlib import Path
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.nlp.kb import TfidfKb

client = TestClient(app)


def get_seed_articles():
    path = Path(__file__).resolve().parent.parent / "data" / "kb_articles.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_tfidf_matcher_relevant_and_unrelated():
    articles = get_seed_articles()
    kb = TfidfKb(articles)

    # 1. Relevant query
    match = kb.match("How do I reset my password?")
    assert match is not None
    assert match.article_id == "kb_pass_01"
    assert "Resetting Your Account Password" in match.title
    assert match.confidence >= settings.kb_suggest_threshold

    # 2. Unrelated text gives low confidence / abstention
    unrelated = kb.match("Where can I buy fresh organic apples?")
    assert unrelated is not None
    assert unrelated.confidence < settings.kb_suggest_threshold


def test_api_kb_suggestion_above_suggest_threshold():
    # Query with moderate confidence (suggestion shown)
    payload = {
        "customer_id": "c9",
        "subject": "Need my past invoice",
        "body": "Where do I find my past receipts and tax invoices?",
        "channel": "web",
    }
    response = client.post("/api/tickets", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["kb"]["confidence"] >= settings.kb_suggest_threshold
    assert data["kb"]["action"] in ("suggest", "auto_reply")
    assert data["kb"]["article_id"] == "kb_inv_02"
    assert data["kb"]["title"] is not None
    assert data["kb"]["source"] is not None


def test_api_kb_abstention_below_threshold():
    # Ticket where KB has no relevant content
    payload = {
        "customer_id": "c11",
        "subject": "Question about office cafeteria",
        "body": "Is the company cafeteria serving vegan pizza on Thursdays?",
        "channel": "web",
    }
    response = client.post("/api/tickets", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["kb"]["confidence"] < settings.kb_suggest_threshold
    assert data["kb"]["action"] == "none"
    assert data["kb"]["article_id"] is None
    assert data["kb"]["title"] is None


def test_api_kb_auto_reply_flow():
    # Ticket with high confidence, routine intent, free tier, low frustration
    payload = {
        "customer_id": "c9",
        "subject": "Resetting Your Account Password",
        "body": "How do I reset my password? Forgot my password what should I do?",
        "channel": "web",
    }
    response = client.post("/api/tickets", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["kb"]["confidence"] >= settings.kb_auto_threshold
    assert data["route"] == "auto_kb"
    assert data["status"] == "kb_handled"
    assert data["kb"]["action"] == "auto_reply"
    assert data["auto_reply"] is not None
    assert "Did this help" in data["auto_reply"]
