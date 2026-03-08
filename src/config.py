"""Application configuration via environment variables or Streamlit secrets."""

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings


def get_streamlit_secrets() -> dict[str, Any]:
    """Get secrets from Streamlit Cloud if available."""
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            return dict(st.secrets)
    except Exception:
        pass
    return {}


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Database
    database_path: str = "data/reconnect.db"
    database_mode: str = "local"  # "local" | "cloud"

    # Supabase (cloud sync)
    supabase_db_url: str = ""  # e.g. "postgresql://postgres:pw@db.xxx.supabase.co:5432/postgres"
    supabase_project_url: str = ""  # e.g. "https://dxaewlecrkcttfziguer.supabase.co"
    supabase_anon_key: str = ""  # For PostgREST access from PWA

    # Action tokens
    action_token_ttl_hours: int = 48  # Token expiry for email action links

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 500
    openai_temperature: float = 0.7

    # Apify (deprecated - use RapidAPI instead)
    apify_api_key: str = ""
    apify_actor_id: str = "2SyF0bVxmgGr8IVCZ"  # LinkedIn Profile Scraper actor

    # RapidAPI - LinkedIn enrichment
    rapidapi_key: str = ""

    # Hunter.io - Email finding and enrichment
    hunter_api_key: str = ""

    # PWA
    pwa_url: str = ""  # Netlify URL, e.g. https://eg-connect.netlify.app

    # Gmail App Password
    gmail_app_password: str = ""  # 16-char app password (spaces stripped)
    gmail_sender_email: str = ""  # Gmail address to send from

    # Telegram Bot notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Pipeline settings
    daily_enrich_budget: int = 30  # Max contacts to enrich per day
    daily_queue_size: int = 20  # Max contacts to add to outreach queue
    prescore_batch_size: int = 50  # Contacts per LLM batch call
    min_queue_score: int = 40  # Minimum reconnect_score to enter outreach queue

    # Exclusion settings
    active_conversation_days: int = 30  # Days to consider conversation "active"
    recently_contacted_days: int = 30  # Days to exclude after contact
    skip_cooldown_days: int = 7  # Days before a skipped contact can re-enter queue

    # LinkedIn import
    linkedin_data_folder: str = "~/Downloads"  # Where to look for LinkedIn exports
    linkedin_export_pattern: str = "LinkedIn Data Export*"  # Glob pattern for exports

    # Email digest
    digest_recipient_email: str = ""  # Override recipient (falls back to Gmail user)
    digest_top_n: int = 5  # Contacts with full draft treatment in digest

    # App settings
    debug: bool = False
    cache_ttl_days: int = 7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Allow extra env vars (e.g. Google service account keys)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
