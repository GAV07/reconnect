"""Gmail integration for Reconnect -- smtplib App Password + OAuth implementation."""

import logging
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from googleapiclient.discovery import build

from src.config import get_settings
from src.database.engine import get_session

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


# --- Gmail OAuth (GCP JSON credentials) ---

GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.send']


def _save_oauth_credentials(google_creds) -> None:
    """Save OAuth tokens to GmailCredentials table."""
    from src.database.models import GmailCredentials

    with get_session() as session:
        stored = session.get(GmailCredentials, 1)
        if not stored:
            stored = GmailCredentials(id=1)

        stored.access_token = google_creds.token
        stored.refresh_token = google_creds.refresh_token
        stored.token_uri = google_creds.token_uri
        stored.client_id = google_creds.client_id
        stored.client_secret = google_creds.client_secret
        stored.scopes = list(google_creds.scopes) if google_creds.scopes else GMAIL_SCOPES
        stored.expiry = google_creds.expiry
        stored.updated_at = datetime.utcnow()

        session.add(stored)
        session.commit()


def _load_oauth_credentials():
    """Load OAuth tokens from GmailCredentials table and refresh if expired."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials as GoogleCredentials

    from src.database.models import GmailCredentials

    with get_session() as session:
        stored = session.get(GmailCredentials, 1)
        if not stored or not stored.refresh_token:
            return None

        creds = GoogleCredentials(
            token=stored.access_token,
            refresh_token=stored.refresh_token,
            token_uri=stored.token_uri,
            client_id=stored.client_id,
            client_secret=stored.client_secret,
            scopes=stored.scopes,
        )
        if stored.expiry:
            creds.expiry = stored.expiry

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_oauth_credentials(creds)
        except Exception as e:
            logger.warning("Gmail OAuth token refresh failed: %s", e)
            return None

    return creds


def authorize_gmail_oauth(client_secrets_path: str) -> None:
    """Run one-time OAuth consent flow. Opens browser for authorization.

    Args:
        client_secrets_path: Path to credentials.json downloaded from GCP Console.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, GMAIL_SCOPES)
    google_creds = flow.run_local_server(port=0)
    _save_oauth_credentials(google_creds)
    logger.info("Gmail OAuth authorized successfully. Tokens saved to database.")


def is_oauth_configured() -> bool:
    """Return True if OAuth tokens exist and are usable."""
    return _load_oauth_credentials() is not None


def oauth_send_html_email(to: str, subject: str, html_body: str) -> dict:
    """Send HTML email via Gmail API using OAuth credentials."""
    import base64

    creds = _load_oauth_credentials()
    if not creds:
        raise ValueError("Gmail OAuth not configured. Run authorize_gmail_oauth() first.")

    service = build('gmail', 'v1', credentials=creds)

    msg = MIMEMultipart('alternative')
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = service.users().messages().send(userId='me', body={'raw': raw}).execute()
    logger.info("OAuth email sent to %s: %s (id: %s)", to, subject, result.get('id', ''))
    return {"sent": True, "message_id": result.get('id', '')}
