"""Test setup: an isolated, freshly seeded SQLite database per test session.

Environment variables are set before any app module is imported, so tests never touch the
demo database (triage.db). Tests run in rules mode for speed; HF tests opt in explicitly.
"""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="triage-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["NLP_MODE"] = "rules"

import pytest  # noqa: E402

from app.config import settings  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    from scripts.seed import seed_database
    seed_database(with_tickets=False)
    yield


@pytest.fixture(autouse=True)
def restore_mode():
    """Evaluation helpers switch settings.nlp_mode; put it back after every test."""
    mode = settings.nlp_mode
    yield
    settings.nlp_mode = mode


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
