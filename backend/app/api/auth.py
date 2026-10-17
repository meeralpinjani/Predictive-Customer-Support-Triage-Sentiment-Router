import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import (
    check_rate_limit, clear_session, record_failure, current_user, current_user_optional, hash_password, require,
    set_session, verify_password,
)
from app.config import PLAN_DEFAULTS, settings
from app.db import get_db
from app.models import Customer, User
from app.schemas import AdminUserPatch, CustomerSummary, GoogleIn, LoginIn, ProfileIn, SignupIn, UserOut

log = logging.getLogger("triage.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])
admin_router = APIRouter(prefix="/api/admin/users", tags=["admin"])


def user_out(db: Session, u: User) -> UserOut:
    cust = db.get(Customer, u.customer_id) if u.customer_id else None
    auth = "both" if (u.password_hash and u.google_sub) else "google" if u.google_sub else "password"
    return UserOut(
        id=u.id, email=u.email, name=u.name, role=u.role, profile_complete=u.profile_complete, auth=auth,
        customer=CustomerSummary(id=cust.id, name=cust.name, segment=cust.segment, plan=cust.plan) if cust else None,
        active=u.active, created_at=u.created_at,
    )


def apply_plan(customer: Customer, plan: str) -> None:
    d = PLAN_DEFAULTS[plan]
    customer.segment = plan
    customer.plan = d["plan"]
    customer.sla_minutes = d["sla_minutes"]
    customer.renewal_days = d["renewal_days"]
    customer.ltv = d["ltv"]


def create_customer_user(db: Session, *, email: str, name: str, plan: str, password: str | None = None,
                         google_sub: str | None = None, profile_complete: bool = True) -> User:
    customer = Customer(id=f"cu-{secrets.token_hex(4)}", name=name, churn_risk=0.2, language="en")
    apply_plan(customer, plan)
    db.add(customer)
    role = "admin" if settings.admin_email and email == settings.admin_email.lower() else "customer"
    user = User(email=email, name=name, role=role, google_sub=google_sub, profile_complete=profile_complete,
                password_hash=hash_password(password) if password else None,
                customer_id=customer.id if role == "customer" else None)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/config")
def auth_config() -> dict:
    return {"google_client_id": settings.google_client_id or None}


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupIn, request: Request, response: Response, db: Session = Depends(get_db)) -> UserOut:
    check_rate_limit(f"signup:{request.client.host if request.client else '?'}", limit=10)
    email = payload.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = create_customer_user(db, email=email, name=payload.name.strip(), plan=payload.plan, password=payload.password)
    set_session(response, user)
    return user_out(db, user)


@router.post("/login", response_model=UserOut)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> UserOut:
    email = payload.email.strip().lower()
    check_rate_limit(f"login:{email}", record=False)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        record_failure(f"login:{email}")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    if not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled")
    set_session(response, user)
    return user_out(db, user)


@router.post("/google", response_model=UserOut)
def google_login(payload: GoogleIn, request: Request, response: Response, db: Session = Depends(get_db)) -> UserOut:
    if not settings.google_client_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Google sign-in is not configured")
    check_rate_limit(f"google:{request.client.host if request.client else '?'}", limit=20)
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
        info = id_token.verify_oauth2_token(payload.credential, google_requests.Request(), settings.google_client_id)
    except Exception as exc:  # invalid, expired, wrong audience, network
        log.warning("Google token rejected: %s", exc)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Google sign-in failed")
    if not info.get("email_verified"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Google account email is not verified")

    email = info["email"].lower()
    user = db.query(User).filter(User.google_sub == info["sub"]).first() or \
        db.query(User).filter(User.email == email).first()
    if user is None:
        # New Google user: they still choose a plan on the next screen.
        user = create_customer_user(db, email=email, name=info.get("name") or email.split("@")[0], plan="free",
                                    google_sub=info["sub"], profile_complete=False)
    elif not user.google_sub:
        user.google_sub = info["sub"]  # link Google to an existing email account
        db.commit()
    if not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled")
    set_session(response, user)
    return user_out(db, user)


@router.post("/logout")
def logout(response: Response) -> dict:
    clear_session(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut | None)
def me(user: User | None = Depends(current_user_optional), db: Session = Depends(get_db)) -> UserOut | None:
    return user_out(db, user) if user else None


@router.patch("/me", response_model=UserOut)
def update_me(payload: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> UserOut:
    if payload.name:
        user.name = payload.name.strip()
    if payload.plan:
        if user.role != "customer" or not user.customer_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only customers have a plan")
        apply_plan(db.get(Customer, user.customer_id), payload.plan)
        user.profile_complete = True
    db.commit()
    return user_out(db, user)


# ---------------------------------------------------------------- admin: users & roles
@admin_router.get("", response_model=list[UserOut])
def list_users(_: User = Depends(require("admin")), db: Session = Depends(get_db)) -> list[UserOut]:
    return [user_out(db, u) for u in db.query(User).order_by(User.role, User.name).all()]


@admin_router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: AdminUserPatch, admin: User = Depends(require("admin")),
                db: Session = Depends(get_db)) -> UserOut:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id and (payload.role not in (None, "admin") or payload.active is False):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't demote or disable yourself")
    if payload.role:
        user.role = payload.role
        if payload.role == "customer" and not user.customer_id:
            c = Customer(id=f"cu-{secrets.token_hex(4)}", name=user.name, churn_risk=0.2)
            apply_plan(c, "free")
            db.add(c)
            user.customer_id = c.id
    if payload.active is not None:
        user.active = payload.active
    if payload.plan:
        if not user.customer_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only customers have a plan")
        apply_plan(db.get(Customer, user.customer_id), payload.plan)
    db.commit()
    return user_out(db, user)
