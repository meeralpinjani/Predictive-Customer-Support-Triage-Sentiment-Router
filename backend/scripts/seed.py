import csv
import json
import logging
from pathlib import Path

from app.db import Base, SessionLocal, engine
from app.models import Agent, Customer, Feedback, KbArticle, Ticket

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("seed")


def get_data_dir() -> Path:
    # Look for data directory relative to this script or current working directory
    base = Path(__file__).resolve().parent.parent / "data"
    if base.exists():
        return base
    cwd_data = Path.cwd() / "data"
    if cwd_data.exists():
        return cwd_data
    cwd_backend_data = Path.cwd() / "backend" / "data"
    if cwd_backend_data.exists():
        return cwd_backend_data
    return base


def seed_database() -> dict[str, int]:
    Base.metadata.create_all(bind=engine)
    data_dir = get_data_dir()
    db = SessionLocal()

    counts = {
        "customers": 0,
        "agents": 0,
        "kb_articles": 0,
        "tickets": 0,
    }

    try:
        # 1. Seed Customers
        customers_path = data_dir / "customers.json"
        if customers_path.exists():
            with open(customers_path, "r", encoding="utf-8") as f:
                customers_data = json.load(f)
            for c in customers_data:
                existing = db.get(Customer, c["id"])
                if not existing:
                    db.add(Customer(
                        id=c["id"],
                        name=c["name"],
                        segment=c["segment"],
                        plan=c.get("plan", ""),
                        sla_minutes=c.get("sla_minutes", 240),
                        renewal_days=c.get("renewal_days", 365),
                    ))
            db.commit()
        counts["customers"] = db.query(Customer).count()

        # 2. Seed Agents (3 Tier 1, 2 Tier 2, 2 Senior)
        if db.query(Agent).count() == 0:
            agents_data = [
                Agent(name="Astrid Lind", level="tier1", skills="general,account"),
                Agent(name="Bjorn Larsson", level="tier1", skills="general"),
                Agent(name="Freja Hansen", level="tier1", skills="account,general"),
                Agent(name="Soren Kierk", level="tier2", skills="billing,technical"),
                Agent(name="Ingrid Bergman", level="tier2", skills="technical,billing"),
                Agent(name="Magnus Carlsen", level="senior", skills="senior,technical,account"),
                Agent(name="Sigrid Undset", level="senior", skills="senior,legal,billing"),
            ]
            db.add_all(agents_data)
            db.commit()
        counts["agents"] = db.query(Agent).count()

        # 3. Seed KB Articles
        kb_path = data_dir / "kb_articles.json"
        if kb_path.exists():
            with open(kb_path, "r", encoding="utf-8") as f:
                kb_data = json.load(f)
            for a in kb_data:
                existing = db.get(KbArticle, a["id"])
                if not existing:
                    db.add(KbArticle(
                        id=a["id"],
                        title=a["title"],
                        questions=json.dumps(a["questions"]),
                        answer=a["answer"],
                        source=a.get("source", "Help Center"),
                    ))
            db.commit()
        counts["kb_articles"] = db.query(KbArticle).count()

        # 4. Seed initial tickets if table is empty
        tickets_path = data_dir / "tickets_seed.csv"
        if tickets_path.exists() and db.query(Ticket).count() == 0:
            with open(tickets_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    db.add(Ticket(
                        customer_id=row.get("customer_id"),
                        subject=row.get("subject", ""),
                        body=row.get("body", ""),
                        channel="web",
                        status="new",
                    ))
            db.commit()
        counts["tickets"] = db.query(Ticket).count()

    finally:
        db.close()

    return counts


if __name__ == "__main__":
    results = seed_database()
    print("Database seeding completed successfully.")
    print("Record counts:")
    for entity, count in results.items():
        print(f"  - {entity}: {count}")
