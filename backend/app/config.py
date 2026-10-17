from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    nlp_mode: str = "rules"                 # rules | hf
    database_url: str = "sqlite:///./triage.db"
    kb_suggest_threshold: float = 0.55
    kb_auto_threshold: float = 0.75
    senior_score: int = 60
    tier2_score: int = 35
    frustration_senior: float = 0.75
    rescore_interval_sec: int = 60
    hf_timeout_sec: float = 3.0
    cors_origins: str = "http://localhost:5173"

settings = Settings()

WEIGHTS: dict[str, float] = {
    "urgency": 0.35,
    "frustration": 0.25,
    "value": 0.15,
    "age": 0.25,
}

SEGMENT_VALUE: dict[str, float] = {
    "enterprise": 1.0,
    "pro": 0.6,
    "basic": 0.3,
    "free": 0.1,
}

UNKNOWN_VALUE: float = 0.3
DEFAULT_SLA_MIN: int = 240
