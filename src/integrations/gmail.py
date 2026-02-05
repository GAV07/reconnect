"""Gmail integration for Reconnect.

Handles OAuth2 authentication and email sending via Gmail API.
"""

import base64
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from src.config import settings
from src.database.engine import get_session
from src.database.models import GmailCredentials


# Gmail API scopes
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",  # For checking sent status
]


def _get_client_config() -> dict:
    """Build OAuth client config from settings."""
    return {
        "web": {
            "client_id": settings.gmail_client_id,
            "client_secret": settings.gmail_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.gmail_redirect_uri],
        }
    }


def is_gmail_configured() -> bool:
    """
    Check if Gmail OAuth is fully configured and valid.

    Returns:
        True if we have valid credentials that can send email
    """
    if not settings.gmail_client_id or not settings.gmail_client_secret:
        return False

    with get_session() as session:
        creds = session.get(GmailCredentials, 1)
        if not creds or not creds.access_token:
            return False

        # Check if token is expired
        if creds.expiry and creds.expiry < datetime.utcnow():
            # Try to refresh
            if creds.refresh_token:
                try:
                    _refresh_credentials()
                    return True
                except Exception:
                    return False
            return False

        return True


def get_gmail_auth_url(state: Optional[str] = None) -> str:
    """
    Generate OAuth URL for Gmail authorization.

    Args:
        state: Optional state parameter for CSRF protection

    Returns:
        Authorization URL to redirect user to
    """
    if not settings.gmail_client_id or not settings.gmail_client_secret:
        raise ValueError("Gmail OAuth not configured. Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET.")

    flow = Flow.from_client_config(
        _get_client_config(),
        scopes=GMAIL_SCOPES,
        redirect_uri=settings.gmail_redirect_uri,
    )

    auth_url, _ = flow.authorization_url(
        access_type="offline",  # Get refresh token
        include_granted_scopes="true",
        prompt="consent",  # Force consent to get refresh token
        state=state,
    )

    return auth_url


def complete_gmail_auth(code: str) -> bool:
    """
    Complete OAuth flow by exchanging code for tokens.

    Args:
        code: Authorization code from OAuth callback

    Returns:
        True if authentication successful
    """
    flow = Flow.from_client_config(
        _get_client_config(),
        scopes=GMAIL_SCOPES,
        redirect_uri=settings.gmail_redirect_uri,
    )

    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Store credentials
    with get_session() as session:
        gmail_creds = session.get(GmailCredentials, 1)
        if not gmail_creds:
            gmail_creds = GmailCredentials(id=1)

        gmail_creds.access_token = credentials.token
        gmail_creds.refresh_token = credentials.refresh_token
        gmail_creds.token_uri = credentials.token_uri
        gmail_creds.client_id = credentials.client_id
        gmail_creds.client_secret = credentials.client_secret
        gmail_creds.scopes = list(credentials.scopes) if credentials.scopes else GMAIL_SCOPES
        gmail_creds.expiry = credentials.expiry
        gmail_creds.updated_at = datetime.utcnow()

        session.add(gmail_creds)

    return True


def _get_credentials() -> Optional[Credentials]:
    """
    Get Google credentials from database.

    Returns:
        Credentials object or None if not configured
    """
    with get_session() as session:
        gmail_creds = session.get(GmailCredentials, 1)
        if not gmail_creds or not gmail_creds.access_token:
            return None

        creds = Credentials(
            token=gmail_creds.access_token,
            refresh_token=gmail_creds.refresh_token,
            token_uri=gmail_creds.token_uri,
            client_id=gmail_creds.client_id or settings.gmail_client_id,
            client_secret=gmail_creds.client_secret or settings.gmail_client_secret,
            scopes=gmail_creds.scopes or GMAIL_SCOPES,
        )

        # Set expiry
        if gmail_creds.expiry:
            creds.expiry = gmail_creds.expiry

        return creds


def _refresh_credentials() -> bool:
    """
    Refresh expired credentials.

    Returns:
        True if refresh successful
    """
    creds = _get_credentials()
    if not creds or not creds.refresh_token:
        return False

    creds.refresh(Request())

    # Update stored credentials
    with get_session() as session:
        gmail_creds = session.get(GmailCredentials, 1)
        if gmail_creds:
            gmail_creds.access_token = creds.token
            gmail_creds.expiry = creds.expiry
            gmail_creds.updated_at = datetime.utcnow()
            session.add(gmail_creds)

    return True


def _get_gmail_service():
    """
    Get authenticated Gmail API service.

    Returns:
        Gmail API service object

    Raises:
        ValueError if not authenticated
    """
    creds = _get_credentials()
    if not creds:
        raise ValueError("Gmail not configured. Complete OAuth flow first.")

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Update stored token
        with get_session() as session:
            gmail_creds = session.get(GmailCredentials, 1)
            if gmail_creds:
                gmail_creds.access_token = creds.token
                gmail_creds.expiry = creds.expiry
                gmail_creds.updated_at = datetime.utcnow()
                session.add(gmail_creds)

    return build("gmail", "v1", credentials=creds)


def send_email(to: str, subject: str, body: str) -> dict:
    """
    Send an email via Gmail API.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body (plain text)

    Returns:
        Dict with message ID and thread ID

    Raises:
        ValueError if Gmail not configured
        Exception on send failure
    """
    service = _get_gmail_service()

    # Create message
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    # Encode for Gmail API
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    # Send
    result = service.users().messages().send(
        userId="me",
        body={"raw": raw}
    ).execute()

    return {
        "message_id": result.get("id"),
        "thread_id": result.get("threadId"),
    }


def get_user_email() -> Optional[str]:
    """
    Get the authenticated user's email address.

    Returns:
        Email address or None if not configured
    """
    try:
        service = _get_gmail_service()
        profile = service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress")
    except Exception:
        return None


def disconnect_gmail() -> bool:
    """
    Remove stored Gmail credentials.

    Returns:
        True if disconnected successfully
    """
    with get_session() as session:
        gmail_creds = session.get(GmailCredentials, 1)
        if gmail_creds:
            gmail_creds.access_token = None
            gmail_creds.refresh_token = None
            gmail_creds.expiry = None
            gmail_creds.updated_at = datetime.utcnow()
            session.add(gmail_creds)

    return True
