"""Phase 1 infrastructure tests.

Tests for:
- Config settings (pwa_url, gmail_app_password, gmail_sender_email)
- Gmail smtplib integration
- Netlify deployment config (stubs -- pass after Plan 02)
- Service worker paths (stubs -- pass after Plan 02)
"""

import pytest


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


def test_pwa_url_config(mock_settings):
    """Settings loads pwa_url from environment variable."""
    from src.config import get_settings
    settings = get_settings()
    assert settings.pwa_url == "https://test.netlify.app"


def test_gmail_config_fields(mock_settings):
    """Settings has gmail_app_password and gmail_sender_email; OAuth fields removed."""
    from src.config import get_settings
    settings = get_settings()

    assert hasattr(settings, "gmail_app_password"), "Settings must have gmail_app_password"
    assert hasattr(settings, "gmail_sender_email"), "Settings must have gmail_sender_email"
    assert not hasattr(settings, "gmail_client_id"), "gmail_client_id must be removed"
    assert not hasattr(settings, "gmail_client_secret"), "gmail_client_secret must be removed"
    assert not hasattr(settings, "gmail_redirect_uri"), "gmail_redirect_uri must be removed"


# ---------------------------------------------------------------------------
# Netlify / PWA infra stubs (will fail until Plan 02)
# ---------------------------------------------------------------------------


def test_netlify_toml():
    """netlify.toml publishes pwa/ dir and has SPA redirect rule."""
    content = open("netlify.toml").read()
    assert 'publish = "pwa"' in content, "netlify.toml must publish pwa/ directory"
    assert 'from = "/*"' in content, "netlify.toml must have SPA redirect rule"


def test_service_worker_paths():
    """service-worker.js uses root-relative paths, no BASE variable.

    NOTE: This test will fail until Plan 02 updates the service worker.
    """
    content = open("pwa/service-worker.js").read()
    assert "const BASE" not in content, "service-worker.js must not use a BASE variable"
    assert (
        "'/index.html'" in content or '"/index.html"' in content
    ), "service-worker.js must reference /index.html with root-relative path"


# ---------------------------------------------------------------------------
# Gmail integration tests
# ---------------------------------------------------------------------------


def test_gmail_is_configured(mock_settings):
    """is_gmail_configured() returns True when both env vars are set."""
    from src.integrations.gmail import is_gmail_configured
    assert is_gmail_configured() is True


def test_gmail_not_configured_without_password(monkeypatch):
    """is_gmail_configured() returns False when GMAIL_APP_PASSWORD is missing."""
    from src.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setenv("GMAIL_SENDER_EMAIL", "test@gmail.com")
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    get_settings.cache_clear()

    from src.integrations.gmail import is_gmail_configured
    assert is_gmail_configured() is False

    get_settings.cache_clear()


def test_gmail_send_html_email(mock_settings, mocker):
    """send_html_email() constructs MIME message, calls SMTP_SSL, returns message_id."""
    mock_smtp_instance = mocker.MagicMock()
    mock_smtp_class = mocker.patch("smtplib.SMTP_SSL")
    mock_smtp_class.return_value.__enter__ = mocker.MagicMock(return_value=mock_smtp_instance)
    mock_smtp_class.return_value.__exit__ = mocker.MagicMock(return_value=False)

    from src.integrations.gmail import send_html_email

    result = send_html_email("to@test.com", "subject", "<h1>body</h1>")

    # SMTP_SSL must be called with the correct host and port
    mock_smtp_class.assert_called_once_with("smtp.gmail.com", 465)

    # login must be called with the sender email and (space-stripped) password
    mock_smtp_instance.login.assert_called_once_with("test@gmail.com", "testpass1234567890")

    # sendmail must be called
    mock_smtp_instance.sendmail.assert_called_once()

    # Return value must include message_id key
    assert "message_id" in result
