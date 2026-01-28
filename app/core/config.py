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

    okx_api_key: str = ""
    okx_api_secret: str = ""
    okx_passphrase: str = ""
    okx_sandbox: bool = True

    # LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""

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
