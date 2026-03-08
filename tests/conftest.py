"""Pytest configuration and shared fixtures for Reconnect tests."""

import pytest

from src.config import get_settings


@pytest.fixture
def mock_settings(monkeypatch):
    """Set environment variables needed for testing and clear the settings cache."""
    # Clear cache before test to ensure fresh settings
    get_settings.cache_clear()

    monkeypatch.setenv("PWA_URL", "https://test.netlify.app")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "testpass1234567890")
    monkeypatch.setenv("GMAIL_SENDER_EMAIL", "test@gmail.com")

    # Clear cache again so next call to get_settings() picks up monkeypatched env
    get_settings.cache_clear()

    yield

    # Clear cache after test to avoid polluting subsequent tests
    get_settings.cache_clear()
