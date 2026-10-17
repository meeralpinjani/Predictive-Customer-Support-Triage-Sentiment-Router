"""Email: free Gmail SMTP (with an app password) when configured, otherwise the admin Outbox.

Every email is recorded in the Outbox table. Sending happens on a background thread so a slow or
offline mail server never blocks the request; failures are recorded, never raised to the user.
"""
import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage

from app.config import settings
from app.db import SessionLocal
from app.models import OutboxEmail

log = logging.getLogger("triage.mail")


def gmail_configured() -> bool:
    return bool(settings.gmail_address and settings.gmail_app_password)


def _send(outbox_id: int, to: str, subject: str, body: str) -> None:
    db = SessionLocal()
    try:
        row = db.get(OutboxEmail, outbox_id)
        try:
            msg = EmailMessage()
            msg["From"] = f"Support Triage Router <{settings.gmail_address}>"
            msg["To"] = to
            msg["Subject"] = subject
            msg.set_content(body)
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=15) as s:
                s.login(settings.gmail_address, settings.gmail_app_password)
                s.send_message(msg)
            row.status = "sent"
        except Exception as exc:  # offline, wrong app password, ...
            log.warning("Email to %s not sent: %s", to, exc)
            row.status, row.error = "failed", str(exc)[:500]
        db.commit()
    finally:
        db.close()


def send_email(db, to: str, subject: str, body: str) -> OutboxEmail:
    row = OutboxEmail(to=to, subject=subject, body=body, status="queued" if gmail_configured() else "outbox_only")
    db.add(row)
    db.commit()
    db.refresh(row)
    if gmail_configured():
        threading.Thread(target=_send, args=(row.id, to, subject, body), daemon=True).start()
    return row
