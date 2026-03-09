"""Phase 2 email reliability tests.

Tests for:
- Email card HTML uses table-based layout (not flexbox)
- Action buttons have 44px+ tap targets (padding >= 12px, font-size 16px)
- Profile link uses query parameter format (?view=contact&id=X)
- LinkedIn button appears only when linkedin_url is set
- Zero instances of display:flex in the HTML output
"""

import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_connection(
    conn_id="conn-123",
    name="Alice Smith",
    linkedin_url="https://linkedin.com/in/alice",
    current_role="VP Engineering",
    current_company="Acme Corp",
    reconnect_score=82.0,
    score_reasoning=None,
):
    """Create a mock Connection object with the needed attributes."""
    conn = MagicMock()
    conn.id = conn_id
    conn.name = name
    conn.linkedin_url = linkedin_url
    conn.current_role = current_role
    conn.current_company = current_company
    conn.reconnect_score = reconnect_score
    conn.pre_score = None
    conn.score_reasoning = score_reasoning
    conn.email = "alice@acme.com"
    conn.enriched_at = None
    return conn


def _make_queue_item(
    item_id=1,
    connection_id="conn-123",
    channel="email",
    status="pending_review",
    why_today="Just published an article on AI",
):
    """Create a mock OutreachQueueItem with the needed attributes."""
    item = MagicMock()
    item.id = item_id
    item.connection_id = connection_id
    item.channel = channel
    item.status = status
    item.why_today = why_today
    return item


FAKE_ACTION_URLS = {
    "approve": "https://test/action?token=a",
    "skip": "https://test/action?token=s",
    "snooze": "https://test/action?token=z",
}
FAKE_FEEDBACK_URL = "https://test/feedback?token=f"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_card_layout_uses_table(mock_settings, mocker):
    """Card header section uses table layout with role="presentation", not flexbox."""
    mocker.patch("src.api.tokens.create_action_tokens", return_value=FAKE_ACTION_URLS)
    mocker.patch("src.api.tokens.create_feedback_token", return_value=FAKE_FEEDBACK_URL)
    mocker.patch(
        "src.integrations.email_digest._get_data_health_stats",
        return_value={"need_email": 0, "need_enrichment": 0, "need_rescoring": 0},
    )
    mocker.patch("src.integrations.email_digest._get_skip_pattern_insight", return_value=None)

    from src.integrations.email_digest import _build_digest_html

    conn = _make_connection()
    queue_item = _make_queue_item()
    contacts = [(queue_item, conn)]

    html = _build_digest_html(contacts, {}, 5)

    # Must use table with role=presentation in card area
    assert '<table' in html, "HTML output must contain table elements"
    assert 'role="presentation"' in html, "Card table must have role=presentation for email clients"
    # Must NOT use flexbox for card layout
    assert 'display:flex' not in html, "Card divs must not use display:flex (stripped by Gmail)"
    assert 'justify-content' not in html, "Card divs must not use justify-content (stripped by Gmail)"


def test_button_tap_targets(mock_settings, mocker):
    """Action buttons have padding >= 12px and font-size 16px for mobile tap targets."""
    mocker.patch("src.api.tokens.create_action_tokens", return_value=FAKE_ACTION_URLS)
    mocker.patch("src.api.tokens.create_feedback_token", return_value=FAKE_FEEDBACK_URL)
    mocker.patch(
        "src.integrations.email_digest._get_data_health_stats",
        return_value={"need_email": 0, "need_enrichment": 0, "need_rescoring": 0},
    )
    mocker.patch("src.integrations.email_digest._get_skip_pattern_insight", return_value=None)

    from src.integrations.email_digest import _build_digest_html

    conn = _make_connection()
    queue_item = _make_queue_item()
    contacts = [(queue_item, conn)]

    html = _build_digest_html(contacts, {}, 5)

    # Buttons must have 12px+ padding (44px tap target) and 16px font size
    # Check that 8px padding from old code is NOT present in action buttons
    assert 'padding:8px' not in html, "Old 8px button padding found — must be 12px+"
    assert 'font-size:13px' not in html, "Old 13px button font size found — must be 16px"
    # Check for 12px padding and 16px font-size in action buttons
    assert 'padding:12px' in html, "Action buttons must have padding:12px (44px tap target)"
    assert 'font-size:16px' in html, "Action buttons must have font-size:16px"


def test_profile_link_uses_query_params(mock_settings, mocker):
    """Profile link uses ?view=contact&id=X query parameters, not hash fragments."""
    mocker.patch("src.api.tokens.create_action_tokens", return_value=FAKE_ACTION_URLS)
    mocker.patch("src.api.tokens.create_feedback_token", return_value=FAKE_FEEDBACK_URL)
    mocker.patch(
        "src.integrations.email_digest._get_data_health_stats",
        return_value={"need_email": 0, "need_enrichment": 0, "need_rescoring": 0},
    )
    mocker.patch("src.integrations.email_digest._get_skip_pattern_insight", return_value=None)

    from src.integrations.email_digest import _build_digest_html

    conn = _make_connection(conn_id="conn-abc-123")
    queue_item = _make_queue_item(connection_id="conn-abc-123")
    contacts = [(queue_item, conn)]

    html = _build_digest_html(contacts, {}, 5)

    # Must use query parameter format for deep link
    assert '?view=contact&amp;id=conn-abc-123' in html or '?view=contact&id=conn-abc-123' in html, \
        "Profile link must use ?view=contact&id= query parameters"
    # Must NOT use hash fragment format
    assert '#/contact/' not in html, "Profile link must not use hash fragment format (stripped by Gmail)"
    # Must use settings.pwa_url as base
    assert 'https://test.netlify.app' in html, "Profile link must use settings.pwa_url as base"


def test_linkedin_button_in_card(mock_settings, mocker):
    """LinkedIn button appears when linkedin_url is set; absent when empty/None."""
    mocker.patch("src.api.tokens.create_action_tokens", return_value=FAKE_ACTION_URLS)
    mocker.patch("src.api.tokens.create_feedback_token", return_value=FAKE_FEEDBACK_URL)
    mocker.patch(
        "src.integrations.email_digest._get_data_health_stats",
        return_value={"need_email": 0, "need_enrichment": 0, "need_rescoring": 0},
    )
    mocker.patch("src.integrations.email_digest._get_skip_pattern_insight", return_value=None)

    from src.integrations.email_digest import _build_digest_html

    # Case 1: linkedin_url is set — LinkedIn button must appear
    conn_with_li = _make_connection(linkedin_url="https://linkedin.com/in/alice")
    queue_item = _make_queue_item()
    contacts_with_li = [(queue_item, conn_with_li)]

    html_with_li = _build_digest_html(contacts_with_li, {}, 5)

    assert 'LinkedIn' in html_with_li, "LinkedIn button must appear when linkedin_url is set"
    assert 'https://linkedin.com/in/alice' in html_with_li, "LinkedIn URL must appear in button href"

    # Case 2: linkedin_url is empty/None — no LinkedIn button
    conn_no_li = _make_connection(linkedin_url=None)
    conn_no_li.linkedin_url = None
    queue_item2 = _make_queue_item()
    contacts_no_li = [(queue_item2, conn_no_li)]

    html_no_li = _build_digest_html(contacts_no_li, {}, 5)

    # LinkedIn button text should not appear as an action button
    # (It's ok if "LinkedIn" appears elsewhere, but the explicit LinkedIn action button should not)
    assert '>LinkedIn<' not in html_no_li, "LinkedIn button must NOT appear when linkedin_url is empty"


def test_no_flexbox_anywhere(mock_settings, mocker):
    """The entire HTML output contains zero instances of display:flex."""
    mocker.patch("src.api.tokens.create_action_tokens", return_value=FAKE_ACTION_URLS)
    mocker.patch("src.api.tokens.create_feedback_token", return_value=FAKE_FEEDBACK_URL)
    mocker.patch(
        "src.integrations.email_digest._get_data_health_stats",
        return_value={"need_email": 0, "need_enrichment": 0, "need_rescoring": 0},
    )
    mocker.patch("src.integrations.email_digest._get_skip_pattern_insight", return_value=None)

    from src.integrations.email_digest import _build_digest_html

    conn = _make_connection()
    queue_item = _make_queue_item()
    contacts = [(queue_item, conn)]

    html = _build_digest_html(contacts, {}, 5)

    assert 'display:flex' not in html, "Found display:flex in output — Gmail strips this on mobile"
    assert 'display: flex' not in html, "Found display: flex (with space) in output — Gmail strips this on mobile"
