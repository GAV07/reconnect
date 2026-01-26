"""Application configuration via environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Database
    database_path: str = "data/reconnect.db"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 500
    openai_temperature: float = 0.7

    # Apify
    apify_api_key: str = ""
    apify_actor_id: str = "2SyF0bVxmgGr8IVCZ"  # LinkedIn Profile Scraper actor

    # Coresignal (placeholder)
    coresignal_api_key: str = ""

    # App settings
    debug: bool = False
    cache_ttl_days: int = 7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
