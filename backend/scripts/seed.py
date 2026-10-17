import csv
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.db import Base, SessionLocal, engine
from app.models import Agent, Customer, KbArticle, Ticket
from app.nlp.kb import reset_kb
from app.schemas import TicketIn
from app.services.triage import process_ticket

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("seed")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

AGENTS = [
    ("Astrid Lind", "tier1", "general,account"),
    ("Bjorn Larsson", "tier1", "general,billing"),
    ("Freja Hansen", "tier1", "account,general,technical"),
    ("Soren Kierk", "tier2", "billing,retention"),
    ("Ingrid Berg", "tier2", "technical,account"),
    ("Magnus Ek", "senior", "senior,technical,account"),
    ("Sigrid Undset", "senior", "senior,legal,billing"),
]
CUSTOMER_FIELDS = ("name", "segment", "plan", "sla_minutes", "renewal_days", "ltv", "churn_risk", "language")


def seed_database(with_tickets: bool = True) -> dict[str, int]:
    """Idempotent: upserts customers/KB, adds agents once, scores seed tickets if none exist."""
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

        if db.query(Agent).count() == 0:
            db.add_all([Agent(name=n, level=lvl, skills=s) for n, lvl, s in AGENTS])
            db.commit()

        for a in json.loads((DATA_DIR / "kb_articles.json").read_text(encoding="utf-8")):
            db.merge(KbArticle(id=a["id"], title=a["title"], questions=json.dumps(a["questions"]),
                               answer=a["answer"], source=a.get("source", "Help Center")))
        db.commit()
        reset_kb()  # rebuild the KB index from the fresh articles on next use

        if with_tickets and db.query(Ticket).count() == 0:
            now = datetime.now(timezone.utc)
            with open(DATA_DIR / "tickets_seed.csv", encoding="utf-8") as f:
                rows = sorted(csv.DictReader(f), key=lambda r: -int(r["minutes_ago"]))
            for r in rows:
                payload = TicketIn(customer_id=r["customer_id"] or None, subject=r["subject"], body=r["body"])
                process_ticket(db, payload, created_at=now - timedelta(minutes=int(r["minutes_ago"])))

        return {
            "customers": db.query(Customer).count(),
            "agents": db.query(Agent).count(),
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
