"""Test setup: an isolated, freshly seeded PostgreSQL schema per test session.

The suite uses the database in DATABASE_URL (backend/.env) or TEST_DATABASE_URL, but creates its own
throwaway schema (test_<random>) inside it and drops it at the end, so the demo data is never touched
and no admin rights are needed. Tests run in rules mode for speed; HF tests opt in explicitly.
"""
import atexit
import os
import secrets
import tempfile
from pathlib import Path

import psycopg


def _env_file_value(name: str) -> str:
    env = Path(__file__).resolve().parents[1] / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return ""


_TMP = Path(tempfile.mkdtemp(prefix="triage-tests-"))
_URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL") or _env_file_value("DATABASE_URL")
if not _URL.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
    raise RuntimeError("Tests need PostgreSQL: set DATABASE_URL in backend/.env (or TEST_DATABASE_URL)")
_PLAIN = _URL.replace("postgresql+psycopg://", "postgresql://").replace("postgres://", "postgresql://", 1)
SCHEMA = f"test_{secrets.token_hex(4)}"
with psycopg.connect(_PLAIN, autocommit=True) as _c:
    _c.execute(f'CREATE SCHEMA "{SCHEMA}"')


@atexit.register
def _drop_schema() -> None:
    try:
        from app.db import engine
        engine.dispose()
    except Exception:
        pass
    with psycopg.connect(_PLAIN, autocommit=True) as c:
        c.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE')


os.environ["DATABASE_URL"] = _URL
os.environ["DATABASE_SCHEMA"] = SCHEMA
os.environ["NLP_MODE"] = "rules"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["ADMIN_EMAIL"] = ""
os.environ["DEMO_PASSWORD"] = ""
os.environ["DEMO_ADMIN_PASSWORD"] = ""
# Optional features start off in tests unless a run switches them on explicitly.
os.environ.setdefault("AI_INTEGRITY_ENABLED", "false")
os.environ.setdefault("AI_INTEGRITY_MODEL_PATH", "")

import pytest  # noqa: E402

from app.config import settings  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    import scripts.seed as seed
    seed.ACCOUNTS_FILE = _TMP / "demo_accounts.json"
    seed.seed_database(with_tickets=False)
    yield


@pytest.fixture(autouse=True)
def restore_mode():
    """Evaluation helpers switch settings.nlp_mode; put it back after every test."""
    from app import auth
    mode = settings.nlp_mode
    auth._attempts.clear()
    yield
    settings.nlp_mode = mode


def _password(email: str) -> str:
    import scripts.seed as seed
    return seed.demo_passwords()[email]


@pytest.fixture
def login():
    """login("admin" | "level1" | "level2" | "level3" | "northwind" | "priya" | "ravi" | "elena") -> client."""
    from fastapi.testclient import TestClient
    from app.main import app

    def _login(who: str):
        c = TestClient(app)
        email = f"{who}@triage.demo"
        res = c.post("/api/auth/login", json={"email": email, "password": _password(email)})
        assert res.status_code == 200, res.text
        return c

    return _login


@pytest.fixture
def anon():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def client(login):
    """An admin client, for tests that just need full access."""
    return login("admin")
