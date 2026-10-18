"""Additive schema changes for databases created by an older version.

The project creates tables with Base.metadata.create_all, which adds new tables but never new
columns to existing ones. These idempotent PostgreSQL statements fill that gap; they only ever add
(no drops, no data changes) and are safe to run on every start-up.
"""
from sqlalchemy import text
from sqlalchemy.engine import Engine

STATEMENTS = [
    "ALTER TABLE attachments ADD COLUMN IF NOT EXISTS content BYTEA",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS client_message_id VARCHAR(64)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_client_id ON messages (ticket_id, author_id, client_message_id)",
]


def upgrade(engine: Engine) -> list[str]:
    with engine.begin() as conn:
        for sql in STATEMENTS:
            conn.execute(text(sql))
    return STATEMENTS


def create_and_upgrade(engine: Engine) -> None:
    from app import models  # noqa: F401  (registers every table on Base.metadata)
    from app.db import Base
    Base.metadata.create_all(bind=engine)
    upgrade(engine)
