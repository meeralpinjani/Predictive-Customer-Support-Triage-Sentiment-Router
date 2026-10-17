"""Accounts: password hashing, signed session cookies and role checks.

- Passwords: scrypt (stdlib) with a per-user salt; never stored or logged in clear.
- Sessions: an HMAC-signed, expiring token in an HttpOnly, SameSite=Lax cookie.
- Roles: customer | level1 | level2 | level3 | admin, enforced on every endpoint.
"""
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User

log = logging.getLogger("triage.auth")

COOKIE = "triage_session"
ROLES = ("customer", "level1", "level2", "level3", "admin")
AGENT_ROLES = ("level1", "level2", "level3")

if not settings.secret_key:
    settings.secret_key = secrets.token_urlsafe(32)
    log.warning("SECRET_KEY not set: generated a temporary one, sessions end when the API restarts")


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        return False
    _, salt_b64, digest_b64 = stored.split("$")
    digest = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), n=2**14, r=8, p=1, dklen=32)
    return hmac.compare_digest(digest, base64.b64decode(digest_b64))


# ---------------------------------------------------------------- sessions
def _sign(payload: bytes) -> str:
    return base64.urlsafe_b64encode(hmac.new(settings.secret_key.encode(), payload, hashlib.sha256).digest()).decode()


def make_token(user_id: int) -> str:
    payload = json.dumps({"uid": user_id, "exp": int(time.time()) + settings.session_days * 86400}).encode()
    return f"{base64.urlsafe_b64encode(payload).decode()}.{_sign(payload)}"


def read_token(token: str) -> int | None:
    try:
        body_b64, sig = token.split(".")
        payload = base64.urlsafe_b64decode(body_b64)
        if not hmac.compare_digest(sig, _sign(payload)):
            return None
        data = json.loads(payload)
        return int(data["uid"]) if data["exp"] > time.time() else None
    except (ValueError, KeyError, TypeError):
        return None


def set_session(response: Response, user: User) -> None:
    response.set_cookie(
        COOKIE, make_token(user.id), max_age=settings.session_days * 86400,
        httponly=True, samesite="lax", secure=settings.cookie_secure, path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


# ---------------------------------------------------------------- login throttling
_attempts: dict[str, deque] = defaultdict(deque)


def check_rate_limit(key: str, limit: int = 8, window_sec: int = 60, record: bool = True) -> None:
    """Raise 429 when `key` has `limit` recorded attempts in the window. With record=False it only
    checks (logins record failures separately, so successful sign-ins never lock anyone out)."""
    now = time.time()
    q = _attempts[key]
    while q and now - q[0] > window_sec:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts, try again in a minute")
    if record:
        q.append(now)


def record_failure(key: str) -> None:
    _attempts[key].append(time.time())


# ---------------------------------------------------------------- dependencies
def current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(COOKIE)
    uid = read_token(token) if token else None
    if uid is None:
        return None
    user = db.get(User, uid)
    return user if user and user.active else None


def current_user(user: User | None = Depends(current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in")
    return user


def require(*roles: str):
    """Dependency factory: the signed-in user must have one of `roles`."""
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this")
        return user
    return dep


def is_agent(user: User) -> bool:
    return user.role in AGENT_ROLES
