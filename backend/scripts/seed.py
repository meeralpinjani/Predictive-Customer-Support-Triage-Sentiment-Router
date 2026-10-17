import csv
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.auth import hash_password
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import Customer, KbArticle, Ticket, User
from app.nlp.kb import reset_kb
from app.schemas import TicketIn
from app.services.triage import process_ticket

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("seed")

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
# Generated per install and git-ignored: never commit real or demo passwords.
ACCOUNTS_FILE = ROOT / "demo_accounts.local.json"

# A few predefined accounts so every role can be shown. Passwords are generated on first seed.
DEMO_ACCOUNTS = [
    {"email": "admin@triage.demo", "name": "Alex Admin", "role": "admin"},
    {"email": "level1@triage.demo", "name": "Astrid Lind", "role": "level1"},
    {"email": "level2@triage.demo", "name": "Ingrid Berg", "role": "level2"},
    {"email": "level3@triage.demo", "name": "Magnus Ek", "role": "level3"},
    {"email": "northwind@triage.demo", "name": "Nora Wind", "role": "customer", "customer_id": "c1"},
    {"email": "priya@triage.demo", "name": "Priya Sharma", "role": "customer", "customer_id": "c14"},
    {"email": "ravi@triage.demo", "name": "Ravi Traders", "role": "customer", "customer_id": "c16"},
    {"email": "elena@triage.demo", "name": "Elena Rostova", "role": "customer", "customer_id": "c9"},
]
CUSTOMER_FIELDS = ("name", "segment", "plan", "sla_minutes", "renewal_days", "ltv", "churn_risk", "language")


def demo_passwords() -> dict[str, str]:
    """Load the generated demo passwords, creating them once if missing."""
    try:
        saved = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    changed = False
    for acc in DEMO_ACCOUNTS:
        if acc["email"] not in saved:
            saved[acc["email"]] = {"role": acc["role"], "password": secrets.token_urlsafe(9)}
            changed = True
    if changed:
        ACCOUNTS_FILE.write_text(json.dumps(saved, indent=2), encoding="utf-8")
    return {email: v["password"] for email, v in saved.items()}


def seed_accounts(db) -> int:
    passwords = demo_passwords()
    for acc in DEMO_ACCOUNTS:
        user = db.query(User).filter(User.email == acc["email"]).first()
        if user is None:
            user = User(email=acc["email"], name=acc["name"], role=acc["role"],
                        customer_id=acc.get("customer_id"), password_hash=hash_password(passwords[acc["email"]]))
            db.add(user)
    db.commit()
    return db.query(User).count()


def seed_database(with_tickets: bool = True) -> dict[str, int]:
    """Idempotent: upserts customers/KB, adds demo accounts once, scores seed tickets if none exist."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for c in json.loads((DATA_DIR / "customers.json").read_text(encoding="utf-8")):
            row = db.get(Customer, c["id"]) or Customer(id=c["id"])
            for k in CUSTOMER_FIELDS:
                if k in c:
                    setattr(row, k, c[k])
            db.merge(row)
        db.commit()

        for a in json.loads((DATA_DIR / "kb_articles.json").read_text(encoding="utf-8")):
            db.merge(KbArticle(id=a["id"], title=a["title"], questions=json.dumps(a["questions"]),
                               answer=a["answer"], source=a.get("source", "Help Center")))
        db.commit()
        reset_kb()  # rebuild the KB index from the fresh articles on next use

        if settings.seed_demo_accounts:
            seed_accounts(db)

        if with_tickets and db.query(Ticket).count() == 0:
            now = datetime.now(timezone.utc)
            owners = {u.customer_id: u for u in db.query(User).filter(User.customer_id.isnot(None)).all()}
            with open(DATA_DIR / "tickets_seed.csv", encoding="utf-8") as f:
                rows = sorted(csv.DictReader(f), key=lambda r: -int(r["minutes_ago"]))
            for r in rows:
                customer = db.get(Customer, r["customer_id"]) if r["customer_id"] else None
                payload = TicketIn(category=r["category"], subject=r["subject"], body=r["body"])
                process_ticket(db, payload, customer, created_by=owners.get(r["customer_id"]),
                               created_at=now - timedelta(minutes=int(r["minutes_ago"])))

        return {
            "customers": db.query(Customer).count(),
            "users": db.query(User).count(),
            "kb_articles": db.query(KbArticle).count(),
            "tickets": db.query(Ticket).count(),
        }
    finally:
        db.close()


if __name__ == "__main__":
    results = seed_database()
    print("Database seeding completed.")
    for entity, count in results.items():
        print(f"  - {entity}: {count}")
    if settings.seed_demo_accounts:
        print(f"Demo account passwords: {ACCOUNTS_FILE}")
