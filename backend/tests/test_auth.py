from app.auth import hash_password, make_token, read_token, verify_password


def test_password_hashing_round_trip():
    h = hash_password("correct horse battery")
    assert h.startswith("scrypt$") and "correct" not in h
    assert verify_password("correct horse battery", h)
    assert not verify_password("wrong", h)
    assert hash_password("same") != hash_password("same")  # salted


def test_session_tokens_are_signed():
    token = make_token(42)
    assert read_token(token) == 42
    body, sig = token.split(".")
    assert read_token(f"{body}.{sig[:-2]}xx") is None
    assert read_token("garbage") is None


def test_signup_with_plan_creates_customer_and_session(anon):
    res = anon.post("/api/auth/signup", json={"name": "Test Pro", "email": "pro@example.com",
                                              "password": "longenough1", "plan": "pro"})
    assert res.status_code == 201
    me = anon.get("/api/auth/me").json()
    assert me["role"] == "customer" and me["customer"]["segment"] == "pro"
    assert me["auth"] == "password"
    # cookie is HttpOnly
    assert "httponly" in res.headers["set-cookie"].lower()


def test_signup_validation_and_duplicates(anon):
    assert anon.post("/api/auth/signup", json={"name": "x", "email": "bad", "password": "longenough1"}).status_code == 422
    assert anon.post("/api/auth/signup", json={"name": "x", "email": "a@b.co", "password": "short"}).status_code == 422
    ok = {"name": "Dup", "email": "dup@example.com", "password": "longenough1"}
    assert anon.post("/api/auth/signup", json=ok).status_code == 201
    assert anon.post("/api/auth/signup", json=ok).status_code == 409


def test_login_logout(anon, login):
    assert anon.post("/api/auth/login", json={"email": "admin@triage.demo", "password": "nope"}).status_code == 401
    c = login("level2")
    assert c.get("/api/auth/me").json()["role"] == "level2"
    c.post("/api/auth/logout")
    assert c.get("/api/auth/me").json() is None


def test_google_is_off_until_configured(anon):
    assert anon.get("/api/auth/config").json()["google_client_id"] is None
    assert anon.post("/api/auth/google", json={"credential": "x" * 20}).status_code == 404


def test_admin_manages_roles(login, anon):
    anon.post("/api/auth/signup", json={"name": "New Agent", "email": "agent@example.com", "password": "longenough1"})
    admin = login("admin")
    users = admin.get("/api/admin/users").json()
    new = next(u for u in users if u["email"] == "agent@example.com")
    res = admin.patch(f"/api/admin/users/{new['id']}", json={"role": "level1"})
    assert res.json()["role"] == "level1"
    me = next(u for u in users if u["email"] == "admin@triage.demo")
    assert admin.patch(f"/api/admin/users/{me['id']}", json={"role": "customer"}).status_code == 400


def test_customer_can_change_plan(login):
    c = login("elena")
    assert c.patch("/api/auth/me", json={"plan": "basic"}).json()["customer"]["segment"] == "basic"
    c.patch("/api/auth/me", json={"plan": "free"})


def test_failed_logins_are_throttled_but_successful_ones_are_not(anon, login):
    for _ in range(3):
        login("level1")                       # repeated successful logins never lock you out
    for _ in range(8):
        anon.post("/api/auth/login", json={"email": "level3@triage.demo", "password": "wrong-password"})
    assert anon.post("/api/auth/login", json={"email": "level3@triage.demo", "password": "wrong-password"}).status_code == 429
