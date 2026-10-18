from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    nlp_mode: str = "hf"                    # hf | rules  (hf falls back to rules automatically)
    database_url: str = ""                  # PostgreSQL only, e.g. postgresql://triage:<password>@localhost:5432/triage
    database_schema: str = ""               # optional schema (the tests use a throwaway one)
    # KB thresholds are per matcher: TF-IDF and MiniLM cosine scores live on different scales.
    # Values chosen by eval/evaluate_kb.py on the validation split (see eval/report.json).
    kb_suggest_threshold: float = 0.43      # TF-IDF (rules mode)
    kb_auto_threshold: float = 0.66
    kb_suggest_threshold_hf: float = 0.46   # MiniLM (hf mode)
    kb_auto_threshold_hf: float = 0.69
    level3_score: int = 65                  # score that escalates to Level 3 (Expert Escalation)
    frustration_senior: float | None = None  # None = threshold fitted by eval/train_frustration.py
    vip_value: float = 0.70                 # "high-value customer" escalation
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
    seed_demo_accounts: bool = True         # predefined demo accounts (scripts/seed.py)
    # Hosted deployments: fixed demo passwords from the environment instead of the local file
    # (the server's disk is wiped on restart). Empty = generate and keep demo_accounts.local.json.
    demo_password: str = ""                 # all demo agents and customers
    demo_admin_password: str = ""           # the demo admin (falls back to demo_password)
    # Files
    max_upload_mb: int = 5
    max_files_per_message: int = 5
    reset_link_minutes: int = 30            # admin-created password reset links
    # Integrity review aid (admins only). See docs/integrity/DECISIONS.md.
    # Values marked PROVISIONAL are not validated: there is no real labelled data yet.
    ai_integrity_enabled: bool = False      # master switch: off = no assessments, ticket behaviour unchanged
    ai_integrity_model_path: str = ""       # local directory of the detector model (never taken from a request)
    ai_integrity_min_words: int = 40        # PROVISIONAL: shorter text -> insufficient_text
    ai_integrity_chunk_size: int = 512      # tokens per window (<= model max length - 2)
    ai_integrity_chunk_overlap: int = 64
    ai_integrity_max_chunks: int = 16       # bounds CPU time per text
    ai_integrity_timeout_seconds: float = 5.0
    ai_integrity_review_threshold: float = 0.80          # PROVISIONAL: mean detector score counted as "AI-like"
    ai_integrity_duplicate_threshold: float = 0.90       # PROVISIONAL: MiniLM cosine for near-identical text
    ai_integrity_duplicate_threshold_tfidf: float = 0.80  # PROVISIONAL: TF-IDF cosine (lower scale)
    ai_integrity_duplicate_window_days: int = 30
    ai_integrity_repeat_window_hours: int = 24           # PROVISIONAL: same-customer repeat window
    ai_integrity_bypass_min_requests: int = 2            # PROVISIONAL
    ai_integrity_max_file_size_mb: int = 10
    ai_integrity_max_document_pages: int = 20
    ai_integrity_max_document_chars: int = 50_000
    ai_integrity_extraction_timeout_seconds: float = 10.0
    ai_integrity_reassess_per_hour: int = 5             # per ticket
    # Ticket summaries and handover. See docs/summaries/DECISIONS.md.
    ticket_summary_enabled: bool = True              # rule-based summaries (handovers work either way)
    ticket_summary_llm_enabled: bool = False         # optional local model refinement (measured: too slow on CPU)
    ticket_summary_llm_model_path: str = ""          # local directory only, never from a request
    ticket_summary_llm_timeout_seconds: float = 10.0
    ticket_summary_max_input_messages: int = 50      # bounded input window
    ticket_summary_reconcile_interval_minutes: int = 60
    ticket_summary_refresh_per_hour: int = 10        # manual refreshes per ticket

    def kb_thresholds(self, mode: str | None = None) -> tuple[float, float]:
        if (mode or self.nlp_mode) == "hf":
            return self.kb_suggest_threshold_hf, self.kb_auto_threshold_hf
        return self.kb_suggest_threshold, self.kb_auto_threshold


settings = Settings()

# Priority = 100 x sum(weight x signal). Weights chosen by eval/tune_weights.py: grid search in the
# queue simulation on five days built only from TRAIN tickets (late replies + waits of urgent,
# highly frustrated and high-value customers). Previous hand-set values: 0.30 / 0.30 / 0.25 / 0.15.
WEIGHTS: dict[str, float] = {
    "frustration": 0.25,
    "urgency": 0.25,
    "value": 0.30,
    "age": 0.20,
}

# Anti-starvation: from 75% of its SLA a waiting ticket ramps up to +SLA_RISK_POINTS (reached at
# 125% of SLA), so it is served before it breaches. Queue order only; routing ignores it.
# Chosen on simulated tuning days (eval/simulate.py, seeds 11 and 23), not the reported day.
SLA_RISK_POINTS: float = 50.0
SLA_RISK_START: float = 0.75
SLA_RISK_FULL: float = 1.25

# Rule boosts.
REPEAT_CONTACT_POINTS: float = 15.0     # 3rd+ ticket from the same customer within 7 days
REPEAT_CONTACT_MIN: int = 3
RENEWAL_RISK_POINTS: float = 10.0       # renewal < 14 days and negative tone
RENEWAL_RISK_DAYS: int = 14

# Customer value model.
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
