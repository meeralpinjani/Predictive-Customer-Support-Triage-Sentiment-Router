from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    nlp_mode: str = "hf"                    # hf | rules  (hf falls back to rules automatically)
    database_url: str = "sqlite:///./triage.db"
    # KB thresholds are per matcher: TF-IDF and MiniLM cosine scores live on different scales.
    # Values chosen by eval/evaluate_kb.py on the validation split (see eval/report.json).
    kb_suggest_threshold: float = 0.43      # TF-IDF (rules mode)
    kb_auto_threshold: float = 0.66
    kb_suggest_threshold_hf: float = 0.46   # MiniLM (hf mode)
    kb_auto_threshold_hf: float = 0.69
    level3_score: int = 65                  # score that escalates to Level 3 (Expert Escalation)
    frustration_senior: float | None = None  # None = threshold fitted by eval/train_frustration.py
    vip_value: float = 0.70                 # "high-value customer" escalation (playbook 10.1)
    vip_score: int = 50
    min_auto_confidence: float = 0.50       # never auto-answer below this NLP confidence
    auto_max_score: int = 40                # auto-answer only below this score
    rescore_interval_sec: int = 30
    hf_timeout_sec: float = 3.0
    cors_origins: str = "http://localhost:5173"
    # Accounts
    secret_key: str = ""                    # signs session cookies; generated per run if empty
    session_days: int = 7
    cookie_secure: bool = False             # set true behind HTTPS
    google_client_id: str = ""              # enables "Sign in with Google" when set
    admin_email: str = ""                   # this address becomes admin on sign-up / login
    seed_demo_accounts: bool = True         # predefined accounts from data/demo_accounts.json
    # Files
    upload_dir: str = "./uploads"           # private: files are only served through the API
    max_upload_mb: int = 5
    max_files_per_message: int = 5
    # Email (free Gmail SMTP with an app password). Without it, emails go to the admin Outbox only.
    gmail_address: str = ""
    gmail_app_password: str = ""
    public_url: str = "http://localhost:5173"   # used to build links in emails
    reset_link_minutes: int = 30

    def kb_thresholds(self, mode: str | None = None) -> tuple[float, float]:
        if (mode or self.nlp_mode) == "hf":
            return self.kb_suggest_threshold_hf, self.kb_auto_threshold_hf
        return self.kb_suggest_threshold, self.kb_auto_threshold


settings = Settings()

# Priority = 100 x sum(weight x signal). Playbook section 9.1.
WEIGHTS: dict[str, float] = {
    "frustration": 0.30,
    "urgency": 0.30,
    "value": 0.25,
    "age": 0.15,
}

# Anti-starvation: from 75% of its SLA a waiting ticket ramps up to +SLA_RISK_POINTS (reached at
# 125% of SLA), so it is served before it breaches. Queue order only; routing ignores it.
# Chosen on simulated tuning days (eval/simulate.py, seeds 11 and 23), not the reported day.
SLA_RISK_POINTS: float = 50.0
SLA_RISK_START: float = 0.75
SLA_RISK_FULL: float = 1.25

# Playbook section 9.4 override rules.
REPEAT_CONTACT_POINTS: float = 15.0     # 3rd+ ticket from the same customer within 7 days
REPEAT_CONTACT_MIN: int = 3
RENEWAL_RISK_POINTS: float = 10.0       # renewal < 14 days and negative tone
RENEWAL_RISK_DAYS: int = 14

# Customer value model, playbook Part 8.
PLAN_VALUE: dict[str, float] = {
    "enterprise": 1.0,
    "pro": 0.6,
    "basic": 0.3,
    "free": 0.1,
}
VALUE_WEIGHTS: dict[str, float] = {"plan": 0.40, "ltv": 0.30, "churn": 0.20, "renewal": 0.10}
LTV_CAP: float = 50_000.0

# CRM defaults for customers who sign up themselves (plan chosen at sign-up).
PLAN_DEFAULTS: dict[str, dict] = {
    "free": {"plan": "Free", "sla_minutes": 480, "renewal_days": None, "ltv": 0.0},
    "basic": {"plan": "Basic", "sla_minutes": 240, "renewal_days": 365, "ltv": 1200.0},
    "pro": {"plan": "Pro", "sla_minutes": 120, "renewal_days": 365, "ltv": 6000.0},
    "enterprise": {"plan": "Enterprise", "sla_minutes": 60, "renewal_days": 365, "ltv": 50000.0},
}

UNKNOWN_VALUE: float = 0.3
DEFAULT_SLA_MIN: int = 240
