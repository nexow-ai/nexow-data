"""Configuration for nexow-data service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service
    port: int = 8001
    environment: str = "development"

    # Oanda API
    oanda_api_url: str = "https://api-fxpractice.oanda.com"
    oanda_account_id: str
    oanda_api_token: str

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_channel: str = "nexow:market:prices"

    # Polling
    poll_interval_seconds: int = 5
    instruments: list[str] = ["EUR_USD", "GBP_USD", "USD_JPY"]


settings = Settings()
