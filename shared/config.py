from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://arenda:arenda@db:5432/arenda"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # JWT
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Telegram Bot
    telegram_bot_token: str = ""

    # Phone parsing
    parse_phones: bool = False
    spfa_api_key: str = ""
    parser_proxy: str = ""
    avito_phone_api_key: str = ""        # переопределяет публичный ключ Avito Mobile API

    # Parser schedule (minutes)
    parser_interval_minutes: int = 3
    cleanup_cron_hour: int = 3           # 03:00 daily
    inactive_ttl_days: int = 3

    # Redis stream names
    stream_listings: str = "listings"
    stream_consumer_group: str = "notification_service"


settings = Settings()
