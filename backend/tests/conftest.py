"""Test setup: an isolated, freshly seeded SQLite database per test session.

Environment variables are set before any app module is imported, so tests never touch the
demo database (triage.db) or the generated demo passwords. Tests run in rules mode for speed;
HF tests opt in explicitly.
"""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="triage-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["NLP_MODE"] = "rules"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["ADMIN_EMAIL"] = ""

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
