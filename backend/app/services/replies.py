"""Suggested agent reply: greeting + empathy matched to the customer's
frustration + the knowledge-base answer or a sensible next step + a concrete follow-up promise.
A draft only: the agent edits it before sending."""
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Customer, KbArticle, Ticket, User
from app.nlp.rules import INTENT_META
from app.services.router import frustration_threshold

NEXT_STEP = {
    "bug": "Could you attach a screenshot of what you see and tell me roughly when it happened? That helps us fix it much faster.",
    "performance": "Could you tell me which page is slow and roughly when it started? A screenshot of any error helps too.",
    "outage": "Our team is already investigating and I'll post updates here as soon as we know more.",
    "billing_dispute": "I'm checking the charge in our billing system now and will confirm the refund reference here.",
    "access": "Let's get you back in. Could you confirm the email you sign in with and whether you see an error message?",
    "cancellation": "I'd like to understand what went wrong before we make any change. Could you tell me a bit more?",
    "complaint": "I've read through your ticket history and I'm taking this on personally from here.",
    "security": "I've treated this as urgent: please don't share your password with anyone, including us. I'm securing your account now.",
    "legal": "I've passed this to the responsible team and will keep you updated here.",
    "safety": "Please stop using the device, unplug it and keep it away from anything flammable. We'll arrange a replacement.",
}


def _empathy(t: Ticket) -> tuple[str, str]:
    high = frustration_threshold(t.analysis_mode)
    if t.frustration >= high:
        return "high", "I'm really sorry about this. I can see how frustrating it has been, and I want to fix it for you."
    if t.frustration >= 0.25:
        return "medium", "Sorry for the trouble, and thank you for your patience."
    return "low", "Thanks for getting in touch."


def _promise(t: Ticket) -> str:
    if t.route == "level3":
        return "I'll update you here within 30 minutes."
    minutes = t.sla_minutes or 240
    return f"I'll update you here within {minutes // 60} hour{'s' if minutes >= 120 else ''}." if minutes >= 60 \
        else f"I'll update you here within {minutes} minutes."


def suggested_reply(db: Session, t: Ticket, agent: User) -> dict:
    customer = db.get(Customer, t.customer_id) if t.customer_id else None
    first = (customer.name.split()[0] if customer else "there")
    tone, empathy = _empathy(t)
    suggest_th, _ = settings.kb_thresholds(t.analysis_mode)

    article = db.get(KbArticle, t.kb_article_id) if t.kb_article_id else None
    flags = [f for f in t.critical_flags.split(",") if f]
    if flags:
        body, basis = NEXT_STEP.get(flags[0], NEXT_STEP["complaint"]), f"critical: {flags[0]}"
    elif article and article.visibility == "public" and t.kb_confidence >= suggest_th:
        if INTENT_META.get(t.intent, {}).get("routine"):
            body = f"Here's how to do it:\n{article.answer}"
        else:  # a problem, not a question: say what we're doing first, then point to the policy
            body = f"{NEXT_STEP.get(t.intent, 'I am looking into this now.')}\n\nFor reference: {article.answer}"
        basis = f"article: {article.title}"
    else:
        body, basis = NEXT_STEP.get(t.intent, "Could you share a few more details so I can help you properly?"), f"intent: {t.intent}"

    parts = {
        "greeting": f"Hi {first},",
        "empathy": empathy,
        "body": body,
        "closing": f"{_promise(t)}\n\nBest regards,\n{agent.name.split()[0]}",
    }
    return {"text": "\n\n".join(parts.values()), "parts": parts, "tone": tone, "basis": basis}
