import json
from pathlib import Path

from app.config import settings
from app.nlp.kb import TfidfKb

SUGGEST, AUTO = settings.kb_thresholds("rules")


def seed_articles():
    path = Path(__file__).resolve().parent.parent / "data" / "kb_articles.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_tfidf_matcher_relevant_and_unrelated():
    kb = TfidfKb(seed_articles())
    match = kb.match("How do I reset my password?")
    assert match.article_id == "kb_pass_01"
    assert match.confidence >= AUTO
    assert kb.match("Where can I buy fresh organic apples?").confidence < SUGGEST


def test_paraphrase_matches_through_single_questions():
    kb = TfidfKb(seed_articles())
    assert kb.match("my credit card expired, how do I add a new one").article_id == "kb_card_17"


def test_api_kb_suggestion(client):
    data = client.post("/api/tickets", json={
        "customer_id": "c9", "category": "billing", "subject": "Need my past invoice",
        "body": "Where do I find my past receipts and tax invoices?",
    }).json()
    assert data["kb"]["confidence"] >= SUGGEST
    assert data["kb"]["action"] in ("suggest", "auto_reply")
    assert data["kb"]["article_id"] == "kb_inv_02"
    assert data["kb"]["title"] and data["kb"]["answer"]


def test_api_kb_abstention_below_threshold(client):
    data = client.post("/api/tickets", json={
        "customer_id": "c11", "category": "howto", "subject": "Question about office cafeteria",
        "body": "Is the company cafeteria serving vegan pizza on Thursdays?",
    }).json()
    assert data["kb"]["confidence"] < SUGGEST
    assert data["kb"]["action"] == "none"
    assert data["kb"]["article_id"] is None


def test_api_kb_auto_reply_flow(client):
    data = client.post("/api/tickets", json={
        "customer_id": "c9", "category": "account", "subject": "Resetting Your Account Password",
        "body": "How do I reset my password? Forgot my password what should I do?",
    }).json()
    assert data["kb"]["confidence"] >= AUTO
    assert data["route"] == "auto_kb" and data["status"] == "kb_handled"
    assert data["assigned_agent"] is None
    assert "Did this help" in data["auto_reply"]


def test_frustrated_customer_is_not_auto_answered(client):
    data = client.post("/api/tickets", json={
        "customer_id": "c9", "category": "account",
        "body": "How do I reset my password?? This is RIDICULOUS, third time asking, I am furious!!!",
    }).json()
    assert data["route"] != "auto_kb"
