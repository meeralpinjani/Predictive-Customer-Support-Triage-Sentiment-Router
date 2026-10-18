"""Wipe the demo database and reseed it: python -m scripts.reset_demo

Seed tickets are scored through the real pipeline with arrival times spread over the last
few hours, so the queue, waits and SLA ageing look like a live support desk.
Restart the API afterwards so its in-memory caches match the fresh data.
"""
from app.schema_upgrade import create_and_upgrade
from app.db import Base, engine
from app.services.rescore import rescore_open
from app.db import SessionLocal
from scripts.seed import seed_database


def reset() -> dict[str, int]:
    from app.config import settings
    if settings.nlp_mode == "hf":
        from app.nlp import hf
        hf.warmup(background=False)  # score the seed tickets with the models, not the fallback
    Base.metadata.drop_all(bind=engine)
    create_and_upgrade(engine)
    counts = seed_database()
    db = SessionLocal()
    try:
        rescore_open(db, publish=False)  # apply ageing for the back-dated tickets
    finally:
        db.close()
    return counts


if __name__ == "__main__":
    counts = reset()
    print("Demo database reset.")
    for k, v in counts.items():
        print(f"  - {k}: {v}")
    from scripts.seed import ACCOUNTS_FILE
    print(f"Demo account passwords: {ACCOUNTS_FILE}")
