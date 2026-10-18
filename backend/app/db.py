"""PostgreSQL connection (the only supported database: local and deployed alike)."""
from collections.abc import Generator
from datetime import timezone

from sqlalchemy import DateTime, create_engine
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


def database_url(url: str) -> str:
    """Hosts hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg driver named."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = database_url(settings.database_url)
if not DATABASE_URL.startswith("postgresql+psycopg://"):
    raise RuntimeError("DATABASE_URL must be a PostgreSQL URL, e.g. postgresql://triage:<password>@localhost:5432/triage "
                       "(set it in backend/.env; see docs/HOW-TO-RUN-AND-TEST.md)")

# DATABASE_SCHEMA (optional) puts every table in one schema; the tests use it to run in an isolated,
# throwaway schema inside the normal database.
_connect = {"options": f"-csearch_path={settings.database_schema}"} if settings.database_schema else {}
# Hosted Postgres (e.g. Neon) closes idle connections: check before use, recycle often, stay small.
engine = create_engine(DATABASE_URL, connect_args=_connect, pool_pre_ping=True, pool_recycle=300,
                       pool_size=5, max_overflow=5)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class UTCDateTime(TypeDecorator):
    """Timestamps are stored as timestamptz and always handed back timezone-aware in UTC, so the API
    never sends a bare timestamp that browsers would read as local time."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
