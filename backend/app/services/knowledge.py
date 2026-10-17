"""Knowledge base: public FAQ articles (auto-answers, help centre) and internal agent guides."""
import json
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import KbArticle, Ticket
from app.services.router import frustration_threshold
from app.services.similarity import TOPIC_THRESHOLD, cluster

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "my", "is", "it", "i", "how", "do", "can",
         "what", "with", "your", "you", "we", "our", "me", "be", "are", "this", "that", "from", "at", "by", "not"}


def questions_of(a: KbArticle) -> list[str]:
    try:
        return json.loads(a.questions)
    except ValueError:
        return [a.questions]


def article_out(a: KbArticle, full: bool = True) -> dict:
    out = {"id": a.id, "title": a.title, "source": a.source, "visibility": a.visibility,
           "tags": [t for t in (a.tags or "").split(",") if t], "updated_at": a.updated_at}
    if full:
        out.update(questions=questions_of(a), answer=a.answer)
    return out


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1}


def text_score(query: str, a: KbArticle) -> float:
    q = _tokens(query)
    if not q:
        return 0.0
    title, body, qs = _tokens(a.title), _tokens(a.answer), _tokens(" ".join(questions_of(a)))
    score = sum(3 if w in title else 2 if w in qs else 1 if w in body else 0 for w in q) / (3 * len(q))
    if query.lower().strip() in a.title.lower():
        score += 0.5
    return round(min(score, 1.0), 3)


def search_articles(db: Session, query: str, include_internal: bool, limit: int = 8) -> list[dict]:
    q = db.query(KbArticle)
    if not include_internal:
        q = q.filter(KbArticle.visibility == "public")
    scored = [(text_score(query, a), a) for a in q.all()]
    # Semantic boost for public articles via the KB index (catches paraphrases with no shared words).
    try:
        from app.services.triage import active_kb
        kb = active_kb(db)
        semantic = {m.article_id: m.confidence for m in kb.rank(query, k=5)} if kb else {}
    except Exception:
        semantic = {}
    ranked = []
    for s, a in scored:
        s = max(s, semantic.get(a.id, 0.0))
        if s >= 0.25:
            ranked.append((s, a))
    ranked.sort(key=lambda x: -x[0])
    return [{**article_out(a), "score": s} for s, a in ranked[:limit]]


def suggest_for_text(db: Session, text: str, k: int = 3) -> list[dict]:
    """'These articles might help' while a customer types a ticket (public articles only)."""
    from app.services.triage import active_kb, kb_thresholds_for
    if len(text.strip()) < 8:
        return []
    kb = active_kb(db)
    if not kb:
        return []
    suggest_th, _ = kb_thresholds_for(kb)
    out = []
    for m in kb.rank(text, k=k):
        if m.confidence >= suggest_th * 0.85:
            out.append({"id": m.article_id, "title": m.title, "answer": m.answer, "source": m.source,
                        "confidence": m.confidence})
    return out


def guides_for_ticket(db: Session, t: Ticket, limit: int = 3) -> list[dict]:
    """Internal guides that fit this ticket: its critical flags, intent and frustration level."""
    wanted = [f for f in t.critical_flags.split(",") if f] + [t.intent]
    if t.frustration >= frustration_threshold(t.analysis_mode):
        wanted.append("frustration")
    guides = db.query(KbArticle).filter(KbArticle.visibility == "internal").all()
    picked = []
    for tag in wanted:
        for g in guides:
            if tag in (g.tags or "").split(",") and g not in picked:
                picked.append(g)
    if t.route in ("level1", "level2"):
        general = next((g for g in guides if "escalation" in (g.tags or "")), None)
        if general and general not in picked:
            picked.append(general)
    return [article_out(g) for g in picked[:limit]]


def topic_suggestions(db: Session, days: int = 30, limit: int = 6) -> dict:
    """Groups of recent tickets the knowledge base could not answer: candidates for new articles."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    suggest_th, _ = settings.kb_thresholds()
    rows = (db.query(Ticket)
            .filter(Ticket.created_at >= since, Ticket.route != "auto_kb", Ticket.kb_confidence < suggest_th)
            .filter(Ticket.critical_flags == "")
            .order_by(Ticket.created_at.desc()).limit(300).all())
    texts = [f"{t.subject}. {t.body}" if t.subject else t.body for t in rows]
    groups, method = cluster(texts, TOPIC_THRESHOLD, min_size=2)
    topics = []
    for g in groups[:limit]:
        members = [rows[i] for i in g]
        words: dict[str, int] = {}
        for i in g:
            for w in _tokens(texts[i]):
                words[w] = words.get(w, 0) + 1
        keywords = [w for w, c in sorted(words.items(), key=lambda x: -x[1]) if c >= 2][:5]
        topics.append({
            "label": (members[0].subject or members[0].body)[:80],
            "keywords": keywords,
            "count": len(members),
            "ticket_ids": [t.id for t in members],
            "examples": [texts[i][:140] for i in g[:3]],
        })
    return {"method": method, "topics": topics, "unanswered_tickets": len(rows)}
