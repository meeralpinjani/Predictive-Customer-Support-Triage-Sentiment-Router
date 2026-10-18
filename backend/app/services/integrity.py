"""Integrity review aid (admins only). See docs/integrity/DECISIONS.md.

Four independent signals per ticket: AI-like writing, near-duplicate text, consistency with this
app's own records, and deterministic manipulation indicators. A versioned, rule-based policy maps
them to a review state. There is no combined fraud score.

Invariants (tested in tests/test_integrity.py):
- never changes a ticket's priority, reply-by time, level, emergency flags, assignment or visibility;
- a detector failure, timeout or absence never blocks ticket creation or replies;
- runs only after the ticket / reply is committed, in a background worker.
"""
from __future__ import annotations

import json
import logging
import queue
import re
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import events
from app.config import settings
from app.db import SessionLocal
from app.models import (Attachment, Customer, IntegrityAssessment, IntegrityReviewAction, Message, Ticket,
                        User)

log = logging.getLogger("triage.integrity")

ASSESSMENT_VERSION = "1"
POLICY_VERSION = "2026-10-18.1"
REVIEW_STATES = ("clear", "review_recommended", "under_review", "confirmed_integrity_concern", "dismissed")
CONSISTENCY_STATES = ("verified_conflict", "possible_inconsistency", "insufficient_evidence", "no_conflict_detected")
ADMIN_STATES = ("under_review", "confirmed_integrity_concern")
STRONG_REASONS = ("verified_conflict", "cross_customer_near_identical")   # plus every manipulation:<code>
WEAK_REASONS = ("ai_pattern", "possible_inconsistency")
MAX_CANDIDATES = 300


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dump(v) -> str:
    return json.dumps(v, separators=(",", ":"))


def load(v: str | None, default=None):
    try:
        return json.loads(v) if v else (default if default is not None else [])
    except ValueError:
        return default if default is not None else []


# ---------------------------------------------------------------- customer content
def customer_texts(db: Session, t: Ticket) -> list[str]:
    """Customer-written text only: subject, description and customer messages (never agent text)."""
    parts = [f"{t.subject or ''}. {t.body or ''}".strip(". ")]
    rows = (db.query(Message).filter(Message.ticket_id == t.id, Message.author_role == "customer",
                                     Message.kind == "message").order_by(Message.created_at).all())
    parts.extend(m.body for m in rows)
    return [p for p in parts if p and p.strip()]


def customer_documents(db: Session, t: Ticket) -> list[Attachment]:
    uploads = (db.query(Attachment).join(User, User.id == Attachment.uploader_id)
               .filter(Attachment.ticket_id == t.id, User.role == "customer").order_by(Attachment.id).all())
    return [a for a in uploads if a.content_type in ("application/pdf", _docx_mime())]


def _docx_mime() -> str:
    from app.nlp.document_extractor import DOCX_MIME
    return DOCX_MIME


# ---------------------------------------------------------------- signal 1: AI-like writing
def ai_signal(text: str) -> dict:
    from app.nlp.ai_authorship import get_detector
    try:
        r = get_detector().assess(text)
    except Exception as exc:  # never let the detector break an assessment
        log.warning("Detector failed: %s", type(exc).__name__)
        from app.nlp.ai_authorship import AuthorshipResult
        r = AuthorshipResult("model_unavailable", reason="detector_error")
    return {"status": r.status, "score": r.score, "score_max": r.score_max, "model_name": r.model_name,
            "model_version": r.model_version, "chunk_count": r.chunk_count, "word_count": r.word_count,
            "reason": r.reason, "limitations": r.limitations}


def document_signals(db: Session, t: Ticket) -> tuple[list[dict], list[str]]:
    """Findings per customer document, plus the extracted texts (kept in memory only, never stored)."""
    from app.nlp.document_extractor import extract
    out, texts = [], []
    for a in customer_documents(db, t):
        ex = extract(a.filename, a.content_type, a.content or b"")
        item = {"attachment_id": a.id, "filename": a.filename, "kind": ex.kind, "status": ex.status,
                "pages": ex.pages, "truncated": ex.truncated, "detail": ex.detail,
                "ai_status": "not_assessed", "ai_score": None}
        if ex.status == "extracted":
            sig = ai_signal(ex.text)          # extracted text is data: only ever scored, never interpreted
            item.update(ai_status=sig["status"], ai_score=sig["score"])
            texts.append(ex.text)
        out.append(item)
    return out, texts


# ---------------------------------------------------------------- signal 2: duplicates
def _ticket_text(t: Ticket) -> str:
    return f"{t.subject or ''}. {t.body or ''}"


def _shared_issue(a: Ticket, b: Ticket) -> bool:
    if a.incident_id and a.incident_id == b.incident_id:
        return True
    outage = lambda x: x.intent == "outage" or "outage" in (x.critical_flags or "")
    return outage(a) and outage(b)


def find_related(db: Session, t: Ticket, viewer: User | None = None) -> tuple[list[dict], str]:
    """Near-identical tickets. Excludes the ticket itself; only tickets `viewer` may see
    (None = the background job, which works with admin visibility)."""
    from app.api.tickets import can_view
    from app.services.similarity import similarity_matrix

    since = utcnow() - timedelta(days=settings.ai_integrity_duplicate_window_days)
    q = (db.query(Ticket).filter(Ticket.id != t.id, Ticket.created_at >= since)
         .order_by(Ticket.created_at.desc()).limit(MAX_CANDIDATES))
    candidates = [c for c in q.all() if viewer is None or can_view(viewer, c)]
    if not candidates:
        return [], "none"
    sims, method = similarity_matrix([_ticket_text(t)] + [_ticket_text(c) for c in candidates])
    threshold = (settings.ai_integrity_duplicate_threshold if method == "minilm"
                 else settings.ai_integrity_duplicate_threshold_tfidf)
    related = []
    for i, c in enumerate(candidates, start=1):
        s = float(sims[0][i])
        if s >= threshold:
            related.append({"ticket_id": c.id, "similarity": round(s, 3), "same_customer": c.customer_id == t.customer_id,
                            "shared_issue": _shared_issue(t, c),
                            "hours_apart": round(abs((t.created_at - c.created_at).total_seconds()) / 3600, 1)})
    related.sort(key=lambda r: -r["similarity"])
    return related, method


def max_similarity(db: Session, t: Ticket) -> float | None:
    """Highest similarity to any other recent ticket, reported even below the duplicate threshold."""
    from app.services.similarity import similarity_matrix
    since = utcnow() - timedelta(days=settings.ai_integrity_duplicate_window_days)
    others = (db.query(Ticket).filter(Ticket.id != t.id, Ticket.created_at >= since)
              .order_by(Ticket.created_at.desc()).limit(MAX_CANDIDATES).all())
    if not others:
        return None
    sims, _ = similarity_matrix([_ticket_text(t)] + [_ticket_text(c) for c in others])
    return round(max(float(x) for x in sims[0][1:]), 3)


# ---------------------------------------------------------------- signal 3: consistency
FIRST_CONTACT = re.compile(r"\b(first time (i'?m |i am |i have |i've )?(contacting|writing|reaching out|contacted)|"
                           r"never (contacted|written to|reached out to|emailed) (you|support|your team)( before)?)\b", re.I)
REPEAT_CONTACT = re.compile(r"\b((second|2nd|third|3rd|fourth|4th|fifth|5th) time|"
                            r"(contacted|written to|emailed) (you|support) (many|several|multiple) times|how many times)\b", re.I)
PLAN_CLAIM = re.compile(r"\b(free|basic|pro|enterprise)\s+(plan|tier|subscription|account|customer)\b", re.I)
MONEY_CLAIM = re.compile(r"\b(charged|refund|payment|billed|deducted|chargeback|invoice amount|paisa|paise)\b", re.I)


def consistency(db: Session, t: Ticket, text: str) -> tuple[str, list[dict]]:
    """Only checks claims against records this app owns. No outside verification source is used."""
    findings = []
    prior = (db.query(Ticket).filter(Ticket.customer_id == t.customer_id, Ticket.id != t.id,
                                     Ticket.created_at < t.created_at).count() if t.customer_id else 0)
    if FIRST_CONTACT.search(text):
        if prior > 0:
            findings.append({"check": "contact_history", "status": "verified_conflict",
                             "detail": f"Says this is the first contact; ticket history has {prior} earlier ticket(s)."})
        else:
            findings.append({"check": "contact_history", "status": "no_conflict_detected",
                             "detail": "Says this is the first contact; no earlier tickets on record."})
    if REPEAT_CONTACT.search(text):
        status = "possible_inconsistency" if prior == 0 else "no_conflict_detected"
        detail = ("Mentions contacting us several times; no earlier tickets on record (may have used another channel)."
                  if prior == 0 else f"Mentions repeated contact; {prior} earlier ticket(s) on record.")
        findings.append({"check": "contact_history", "status": status, "detail": detail})
    customer = db.get(Customer, t.customer_id) if t.customer_id else None
    claims = {m.group(1).lower() for m in PLAN_CLAIM.finditer(text)}
    if claims and customer is not None:
        on_file = (customer.segment or "").lower()
        if on_file and on_file not in claims:
            findings.append({"check": "plan", "status": "possible_inconsistency",
                             "detail": f"Mentions a {'/'.join(sorted(claims))} plan; the plan on file is {on_file}."})
        else:
            findings.append({"check": "plan", "status": "no_conflict_detected", "detail": "Plan mentioned matches the record."})
    if MONEY_CLAIM.search(text):
        findings.append({"check": "payments", "status": "insufficient_evidence",
                         "detail": "Mentions a payment or refund; this system holds no payment records to compare."})
    if not findings:
        return "no_conflict_detected", []
    order = {s: i for i, s in enumerate(CONSISTENCY_STATES)}
    overall = min((f["status"] for f in findings), key=lambda s: order[s])
    return overall, findings


# ---------------------------------------------------------------- signal 4: manipulation indicators
BYPASS = re.compile(r"\b(skip|bypass|avoid|without|no need (for|to)|don'?t (do|need|run|bother with))\b[^.?!\n]{0,30}?"
                    r"\b(verification|verify|verifying|review|reviews|checks?|checking|approval|kyc)\b", re.I)
AUTOMATION = re.compile(r"\b(ignore (all |any )?(previous|prior|above|earlier) instructions|system prompt|"
                        r"disregard (your|the|all) (rules|instructions|policy)|you are (an|a) (ai|bot|language model)|"
                        r"developer mode|mark (this|the|my) ticket as (clear|resolved|safe|approved))\b", re.I)


def manipulation_indicators(texts: list[str], related: list[dict], t: Ticket) -> list[dict]:
    """Deterministic rules only. Capitals, anger, urgency, formality, grammar, non-native English
    and AI or translation use are never indicators."""
    found = []
    repeats = [r for r in related if r["same_customer"] and r["hours_apart"] <= settings.ai_integrity_repeat_window_hours]
    if repeats:
        found.append({"code": "repeat_near_identical_submission", "count": len(repeats), "threshold": 1,
                      "detail": f"{len(repeats)} near-identical ticket(s) from the same customer within "
                                f"{settings.ai_integrity_repeat_window_hours} h."})
    bypass = sum(len(BYPASS.findall(x)) for x in texts)
    if bypass >= settings.ai_integrity_bypass_min_requests:
        found.append({"code": "review_bypass_requests", "count": bypass,
                      "threshold": settings.ai_integrity_bypass_min_requests,
                      "detail": f"{bypass} requests to skip or bypass checks."})
    auto = sum(len(AUTOMATION.findall(x)) for x in texts)
    if auto:
        found.append({"code": "instructions_aimed_at_automation", "count": auto, "threshold": 1,
                      "detail": "Text addresses an automated system with instructions; it was treated as data only."})
    return found


# ---------------------------------------------------------------- policy
@dataclass
class PolicyResult:
    review_state: str
    reasons: list[str]


def policy(ai: dict, documents: list[dict], related: list[dict], consistency_status: str,
           indicators: list[dict], previous: IntegrityAssessment | None = None) -> PolicyResult:
    reasons = []
    if consistency_status == "verified_conflict":
        reasons.append("verified_conflict")
    if consistency_status == "possible_inconsistency":
        reasons.append("possible_inconsistency")
    reasons += [f"manipulation:{i['code']}" for i in indicators]
    if any(not r["same_customer"] and not r["shared_issue"] for r in related):
        reasons.append("cross_customer_near_identical")
    th = settings.ai_integrity_review_threshold
    if (ai["status"] == "assessed" and ai["score"] is not None and ai["score"] >= th) or \
            any(d["ai_status"] == "assessed" and (d["ai_score"] or 0) >= th for d in documents):
        reasons.append("ai_pattern")
    strong = [r for r in reasons if r in STRONG_REASONS or r.startswith("manipulation:")]
    weak = [r for r in reasons if r in WEAK_REASONS]
    state = "review_recommended" if strong or len(weak) >= 2 else "clear"   # AI patterns alone never recommend review
    if previous is not None:
        if previous.review_state in ADMIN_STATES:
            state = previous.review_state
        elif previous.review_state == "dismissed":
            new = set(reasons) - set(load(previous.policy_reasons))
            state = state if (new and state == "review_recommended") else "dismissed"
    return PolicyResult(state, reasons)


# ---------------------------------------------------------------- scheduling
def schedule(ticket_id: int, trigger: str, key: str) -> int | None:
    """Create a pending assessment after the ticket/reply is committed and queue it.
    Never raises: integrity problems must not affect the customer's request."""
    if not settings.ai_integrity_enabled:
        return None
    try:
        with SessionLocal() as db:
            row = IntegrityAssessment(ticket_id=ticket_id, trigger=trigger, trigger_key=key, status="pending",
                                      assessment_version=ASSESSMENT_VERSION, policy_version=POLICY_VERSION)
            db.add(row)
            try:
                db.commit()
            except IntegrityError:          # same trigger already scheduled (retry): nothing to do
                db.rollback()
                return None
            aid = row.id
        runner.submit(aid)
        return aid
    except Exception as exc:
        log.warning("Could not schedule integrity assessment: %s", type(exc).__name__)
        return None


def manual_key() -> str:
    return f"manual:{secrets.token_hex(8)}"


def run_assessment(assessment_id: int) -> None:
    with SessionLocal() as db:
        row = db.get(IntegrityAssessment, assessment_id)
        if row is None or row.status != "pending":
            return
        try:
            _assess(db, row)
            row.status = "complete"
        except Exception as exc:
            db.rollback()
            row = db.get(IntegrityAssessment, assessment_id)
            row.status, row.error = "error", type(exc).__name__
            log.warning("Integrity assessment %s failed: %s", assessment_id, type(exc).__name__)
        row.updated_at = utcnow()
        db.commit()
        events.publish({"type": "integrity.assessed", "assessment_id": row.id, "ticket_id": row.ticket_id,
                        "status": row.status, "review_state": row.review_state, "ai_status": row.ai_status,
                        "customer_id": None, "route": None, "old_route": None, "assigned_agent_id": None})


def _assess(db: Session, row: IntegrityAssessment) -> None:
    t = db.get(Ticket, row.ticket_id)
    if t is None:
        raise LookupError("ticket missing")
    texts = customer_texts(db, t)
    joined = "\n".join(texts)
    ai = ai_signal(joined)
    documents, doc_texts = document_signals(db, t)
    related, method = find_related(db, t)
    status, findings = consistency(db, t, joined)
    indicators = manipulation_indicators(texts + doc_texts, related, t)
    previous = (db.query(IntegrityAssessment)
                .filter(IntegrityAssessment.ticket_id == t.id, IntegrityAssessment.id != row.id,
                        IntegrityAssessment.status == "complete")
                .order_by(IntegrityAssessment.id.desc()).first())
    result = policy(ai, documents, related, status, indicators, previous)
    row.model_name, row.model_version = ai["model_name"], ai["model_version"]
    row.ai_status, row.ai_score, row.ai_score_max = ai["status"], ai["score"], ai["score_max"]
    row.ai_chunk_count, row.ai_word_count, row.ai_reason = ai["chunk_count"], ai["word_count"], ai["reason"]
    row.duplicate_method = method
    row.duplicate_max_similarity = max_similarity(db, t)
    row.related_ticket_ids = _dump(related)
    row.consistency_status, row.consistency_findings = status, _dump(findings)
    row.manipulation_indicators = _dump(indicators)
    row.document_findings = _dump(documents)
    row.policy_reasons = _dump(result.reasons)
    row.review_state = result.review_state
    row.review_recommended = result.review_state == "review_recommended"


# ---------------------------------------------------------------- review actions
ACTION_TARGET = {"start_review": "under_review", "dismiss": "dismissed", "confirm": "confirmed_integrity_concern"}


def review(db: Session, row: IntegrityAssessment, actor: User, action: str, reason: str) -> IntegrityReviewAction:
    """Record an admin decision. Assessment results stay as computed; only review_state changes,
    and every change is audited."""
    act = IntegrityReviewAction(assessment_id=row.id, actor_id=actor.id, action=action, reason=reason)
    db.add(act)
    row.review_state = ACTION_TARGET[action]
    row.review_recommended = False
    row.updated_at = utcnow()
    db.commit()
    log.info("integrity review action=%s assessment=%s ticket=%s actor=%s", action, row.id, row.ticket_id, actor.id)
    events.publish({"type": "integrity.review_updated", "assessment_id": row.id, "ticket_id": row.ticket_id,
                    "review_state": row.review_state, "customer_id": None, "route": None, "old_route": None,
                    "assigned_agent_id": None})
    return act


# ---------------------------------------------------------------- background worker
class BackgroundRunner:
    """One daemon thread and a bounded queue. Not durable: pending rows are re-queued at start-up
    and can always be re-run with the reassess endpoint."""

    def __init__(self, maxsize: int = 200) -> None:
        self.q: queue.Queue = queue.Queue(maxsize=maxsize)
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._loop, name="integrity-worker", daemon=True)
            self.thread.start()

    def stop(self) -> None:
        if self.thread is not None and self.thread.is_alive():
            self.q.put(None)
            self.thread.join(timeout=5)

    def submit(self, assessment_id: int) -> None:
        self.start()
        try:
            self.q.put_nowait(assessment_id)
        except queue.Full:
            log.warning("Integrity queue full; assessment %s stays pending", assessment_id)

    def _loop(self) -> None:
        while True:
            aid = self.q.get()
            if aid is None:
                return
            try:
                run_assessment(aid)
            except Exception as exc:
                log.warning("Integrity worker error: %s", type(exc).__name__)


runner = BackgroundRunner()


def startup() -> None:
    if not settings.ai_integrity_enabled:
        return
    from app.nlp.ai_authorship import startup_check
    log.info("Integrity analyzer enabled; detector check: %s", startup_check())
    runner.start()
    with SessionLocal() as db:
        for (aid,) in db.query(IntegrityAssessment.id).filter(IntegrityAssessment.status == "pending").all():
            runner.submit(aid)


def shutdown() -> None:
    runner.stop()
