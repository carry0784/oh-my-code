from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/trading"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/trading"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Exchange
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True

    upbit_api_key: str = ""
    upbit_api_secret: str = ""

    bitget_api_key: str = ""
    bitget_api_secret: str = ""
    bitget_passphrase: str = ""
    bitget_sandbox: bool = True

    # KIS (한국투자증권)
    kis_app_key: str = ""
    kis_app_secret: str = ""
    kis_account_no: str = ""
    kis_account_suffix: str = "01"
    kis_demo: bool = True

    # Kiwoom (키움증권)
    kiwoom_app_key: str = ""
    kiwoom_app_secret: str = ""
    kiwoom_account_no: str = ""
    kiwoom_account_suffix: str = "01"
    kiwoom_demo: bool = True

    # LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Governance
    # Default True — must be explicitly disabled. Production requires True.
    governance_enabled: bool = True

    # Evidence persistence
    # Empty = InMemoryBackend (NOT_DURABLE). Path = SQLiteBackend (DURABLE).
    evidence_db_path: str = ""

    # C-19: Receipt file persistence
    # Empty = in-memory only (lost on restart). Path = JSONL file backend (DURABLE).
    receipt_file_path: str = ""

    # C-20: External notifier webhook
    # Empty = disabled. URL = send incident snapshots to webhook endpoint.
    notifier_webhook_url: str = ""

    # C-27: Multi-notifier channels
    # Empty = disabled. Path = append incident JSONL to file.
    notifier_file_path: str = ""
    # Empty = disabled. URL = send to Slack webhook.
    notifier_slack_url: str = ""

    # Logging
    # Empty = STREAM_ONLY (stdout). Path = FILE_PERSISTED (stdout + rotating file).
    log_file_path: str = ""
    log_level: str = "INFO"

    # Trading
    default_exchange: str = "binance"
    max_position_size_usd: float = 1000.0
    risk_limit_percent: float = 2.0

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
