"""Gmail integration for Reconnect -- smtplib App Password implementation."""

import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from src.config import get_settings

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465  # SSL


def is_gmail_configured() -> bool:
    """Check if Gmail App Password is configured."""
    s = get_settings()
    return bool(s.gmail_app_password and s.gmail_sender_email)


def get_user_email() -> Optional[str]:
    """Return the configured sender email address."""
    return get_settings().gmail_sender_email or None


def send_html_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> dict:
    """Send an HTML email via Gmail SMTP with App Password auth."""
    if not is_gmail_configured():
        raise ValueError(
            "Gmail not configured. Set GMAIL_APP_PASSWORD and GMAIL_SENDER_EMAIL in .env"
        )

    s = get_settings()

    if text_body is None:
        text_body = re.sub(r"<[^>]+>", "", html_body)
        text_body = re.sub(r"\n\s*\n", "\n\n", text_body).strip()

    msg = MIMEMultipart("alternative")
    msg["From"] = s.gmail_sender_email
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    password = s.gmail_app_password.replace(" ", "")

    with smtplib.SMTP_SSL(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as server:
        server.login(s.gmail_sender_email, password)
        server.sendmail(s.gmail_sender_email, to, msg.as_string())
        logger.info("Email sent to %s: %s", to, subject)

    return {"message_id": msg.get("Message-ID", "")}
