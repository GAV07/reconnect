"""Phase 8 email signal UI tests — full test scaffold.

Covers:
- TestDigestRebuild: Rebuilt email digest (EMAIL-01 through EMAIL-04)
- TestPipelineWiring: Telegram still wired in daily_pipeline.py
- TestSignalWrite: Signal write / user priority (Plan 02 — skipped)
- TestProfileFallback: Profile key factors / starters (Plan 03 — skipped)
- TestNoteWrite: Contact note insert (Plan 03 — skipped)
- TestQueueCardContext: Queue card context fields (Plan 02 — skipped)
- TestPullSync: Pull sync signal keys (Plan 04 — skipped)
"""

import pytest
from unittest.mock import MagicMock, patch


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
    raw_enrichment=None,
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
    conn.raw_enrichment = raw_enrichment
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


def _build_html_for_test(contacts=None, pipeline_results=None, top_n=5, mock_settings_fixture=None):
    """Helper: call _build_digest_html with sensible defaults."""
    from src.integrations.email_digest import _build_digest_html

    if contacts is None:
        conn = _make_connection()
        queue_item = _make_queue_item()
        contacts = [(queue_item, conn)]
    if pipeline_results is None:
        pipeline_results = {}
    return _build_digest_html(contacts, pipeline_results, top_n)


# ---------------------------------------------------------------------------
# TestDigestRebuild — EMAIL-01 through EMAIL-04
# ---------------------------------------------------------------------------


class TestDigestRebuild:
    """Tests for the rebuilt email digest: CTA, no legacy buttons, industry chips."""

    def test_review_in_app_cta_present(self, mock_settings):
        """_build_digest_html output contains 'Review in App' text and ?view=queue URL."""
        html = _build_html_for_test()
        assert "Review in App" in html, "Email must contain 'Review in App' CTA text"
        assert "?view=queue" in html, "CTA must link to ?view=queue deep link"

    def test_no_legacy_action_buttons(self, mock_settings):
        """Output does NOT contain Approve/Skip/Snooze button text."""
        html = _build_html_for_test()
        # These were the old per-contact action button labels
        assert ">Approve<" not in html, "Approve button must not appear in rebuilt digest"
        assert ">Yes<" not in html, "Yes/Approve button must not appear in rebuilt digest"
        assert ">Skip<" not in html, "Skip button must not appear in rebuilt digest"
        assert ">Snooze<" not in html, "Snooze button must not appear in rebuilt digest"

    def test_no_token_generation(self, mock_settings):
        """_build_digest_html does NOT call create_action_tokens or create_feedback_token."""
        call_log = []

        def fail_if_called(*args, **kwargs):
            call_log.append("called")
            raise AssertionError("create_action_tokens must not be called in rebuilt digest")

        with patch("src.api.tokens.create_action_tokens", side_effect=fail_if_called):
            with patch("src.api.tokens.create_feedback_token", side_effect=fail_if_called):
                html = _build_html_for_test()

        assert len(call_log) == 0, "Token generation functions must not be called"
        assert html  # ensure HTML was produced

    def test_no_data_health_section(self, mock_settings):
        """Output does NOT contain 'Your Network Data' text."""
        html = _build_html_for_test()
        assert "Your Network Data" not in html, (
            "Data health section must be removed from rebuilt digest"
        )

    def test_no_feedback_stars(self, mock_settings):
        """Output does NOT contain 'Was today's digest useful?' text."""
        html = _build_html_for_test()
        assert "Was today" not in html and "digest useful" not in html, (
            "Feedback stars section must be removed from rebuilt digest"
        )

    def test_industry_in_featured_cards(self, mock_settings):
        """Output contains industry text when connection has raw_enrichment with company_industry."""
        conn = _make_connection(
            raw_enrichment={"data": {"company_industry": "Technology"}}
        )
        queue_item = _make_queue_item()
        contacts = [(queue_item, conn)]
        html = _build_html_for_test(contacts=contacts)
        assert "Technology" in html, (
            "Industry chip must appear when raw_enrichment has company_industry"
        )

    def test_industry_in_featured_cards_top_level(self, mock_settings):
        """Output contains industry text when raw_enrichment has top-level company_industry."""
        conn = _make_connection(
            raw_enrichment={"company_industry": "Finance"}
        )
        queue_item = _make_queue_item()
        contacts = [(queue_item, conn)]
        html = _build_html_for_test(contacts=contacts)
        assert "Finance" in html, (
            "Industry chip must appear for top-level company_industry in raw_enrichment"
        )

    def test_digest_subject_format(self, mock_settings, mocker):
        """send_digest_email() produces subject like 'Reconnect Mar 4: Name1, Name2 + N more'."""
        mocker.patch(
            "src.integrations.email_digest._get_digest_contacts",
            return_value=[
                (_make_queue_item(item_id=i, connection_id=f"c-{i}"), _make_connection(conn_id=f"c-{i}", name=n))
                for i, n in enumerate(["Sarah Jones", "Mike Brown", "Lisa Chen", "Bob Davis"], 1)
            ],
        )
        mocker.patch("src.integrations.email_digest.is_oauth_configured", return_value=False)
        mocker.patch("src.integrations.email_digest.is_gmail_configured", return_value=True)
        mocker.patch("src.integrations.email_digest.get_user_email", return_value="user@example.com")

        captured = {}

        def fake_send_html_email(recipient, subject, html_body):
            captured["subject"] = subject
            captured["recipient"] = recipient
            return {"message_id": "fake-id"}

        mocker.patch("src.integrations.email_digest.send_html_email", side_effect=fake_send_html_email)

        from src.integrations.email_digest import send_digest_email
        result = send_digest_email({})

        assert "subject" in captured, "send_html_email was not called"
        subject = captured["subject"]
        assert subject.startswith("Reconnect "), f"Subject must start with 'Reconnect ': {subject}"
        assert "Sarah" in subject, f"Subject must include first contact name: {subject}"
        assert "+ 1 more" in subject, f"Subject must include '+ N more': {subject}"

    def test_send_digest_email_returns_dict(self, mock_settings, mocker):
        """send_digest_email() returns dict with sent, recipient, contacts keys."""
        mocker.patch(
            "src.integrations.email_digest._get_digest_contacts",
            return_value=[
                (_make_queue_item(), _make_connection())
            ],
        )
        mocker.patch("src.integrations.email_digest.is_oauth_configured", return_value=False)
        mocker.patch("src.integrations.email_digest.is_gmail_configured", return_value=True)
        mocker.patch("src.integrations.email_digest.get_user_email", return_value="user@example.com")
        mocker.patch(
            "src.integrations.email_digest.send_html_email",
            return_value={"message_id": "fake-id"},
        )

        from src.integrations.email_digest import send_digest_email
        result = send_digest_email({})

        assert isinstance(result, dict), "send_digest_email must return a dict"
        assert "sent" in result, "Result must have 'sent' key"
        assert "recipient" in result, "Result must have 'recipient' key"
        assert "contacts" in result, "Result must have 'contacts' key"

    def test_featured_cards_have_profile_deep_link(self, mock_settings):
        """Output contains ?view=contact&id= for profile links."""
        conn = _make_connection(conn_id="conn-abc-456")
        queue_item = _make_queue_item(connection_id="conn-abc-456")
        contacts = [(queue_item, conn)]
        html = _build_html_for_test(contacts=contacts)

        assert "?view=contact" in html, "Profile deep link must use ?view=contact query param"
        assert "conn-abc-456" in html, "Profile deep link must include connection ID"

    def test_remaining_list_preserved(self, mock_settings):
        """Remaining contacts appear as compact list when > top_n contacts."""
        contacts = [
            (_make_queue_item(item_id=i, connection_id=f"c-{i}"), _make_connection(conn_id=f"c-{i}", name=f"Person {i}"))
            for i in range(1, 8)
        ]
        html = _build_html_for_test(contacts=contacts, top_n=3)

        assert "more in queue" in html, "Remaining contacts list must appear when > top_n contacts"
        # 7 contacts with top_n=3 means 4 remaining
        assert "4 more" in html, "Must show correct count of remaining contacts"


# ---------------------------------------------------------------------------
# TestPipelineWiring
# ---------------------------------------------------------------------------


class TestPipelineWiring:
    """Tests that Telegram notification remains wired in daily_pipeline.py."""

    def test_telegram_wired(self):
        """Telegram import exists in daily_pipeline.py."""
        import ast
        import os

        pipeline_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "src", "pipeline", "daily_pipeline.py"
        )
        assert os.path.exists(pipeline_path), "daily_pipeline.py must exist"

        with open(pipeline_path) as f:
            source = f.read()

        assert "telegram" in source.lower(), (
            "daily_pipeline.py must import/reference telegram for notifications"
        )


# ---------------------------------------------------------------------------
# TestSignalWrite — Plan 02 stubs
# ---------------------------------------------------------------------------


class TestSignalWrite:
    """Signal write / user priority tests — implemented in Plan 02."""

    @pytest.mark.skip(reason="Plan 02")
    def test_archive_sets_user_priority(self):
        """Archive action sets user_priority signal on connection."""
        pass


# ---------------------------------------------------------------------------
# TestProfileFallback — Plan 03 stubs
# ---------------------------------------------------------------------------


class TestProfileFallback:
    """Profile key factors / starters fallback — implemented in Plan 03."""

    @pytest.mark.skip(reason="Plan 03")
    def test_key_factors_fallback_with_enrichment(self):
        """Key factors section falls back to enrichment data when score_reasoning is absent."""
        pass

    @pytest.mark.skip(reason="Plan 03")
    def test_key_factors_fallback_truly_empty(self):
        """Key factors section shows empty state when no data available."""
        pass

    @pytest.mark.skip(reason="Plan 03")
    def test_starters_fallback_uses_headline(self):
        """Conversation starters use LinkedIn headline as fallback."""
        pass


# ---------------------------------------------------------------------------
# TestNoteWrite — Plan 03 stubs
# ---------------------------------------------------------------------------


class TestNoteWrite:
    """Contact note insert — implemented in Plan 03."""

    @pytest.mark.skip(reason="Plan 03")
    def test_contact_note_insert_structure(self):
        """Contact note is inserted with correct structure via PostgREST."""
        pass


# ---------------------------------------------------------------------------
# TestQueueCardContext — Plan 02 stubs
# ---------------------------------------------------------------------------


class TestQueueCardContext:
    """Queue card context fields — implemented in Plan 02."""

    @pytest.mark.skip(reason="Plan 02")
    def test_card_context_fields_populated(self):
        """Queue card context fields are populated from signal and why_today."""
        pass


# ---------------------------------------------------------------------------
# TestPullSync — Plan 04 / wave 1 stubs
# ---------------------------------------------------------------------------


class TestPullSync:
    """Pull sync signal keys — implemented in Plan 04 / wave 1."""

    @pytest.mark.skip(reason="Plan 04 / wave 1")
    def test_pull_stats_has_signal_keys(self):
        """Pull sync stats include signal-related keys."""
        pass
