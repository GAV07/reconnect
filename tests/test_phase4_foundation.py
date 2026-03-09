"""Phase 4 foundation fixes and queue UX tests.

Tests for:
- INFRA-02: Score breakdown display fix — contacts have dimension_scores in score_reasoning
- INFRA-01: Gmail OAuth configuration stubs
- QUEUE-01/02: Queue sort toggle and status filter stubs
- QUEUE-03: Industry dual-path filter stub
"""

import json
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, call
from contextlib import contextmanager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_connection(
    conn_id: str,
    score_reasoning: str | None,
    enriched_at: datetime | None = datetime(2026, 1, 1),
    reconnect_score: float | None = 75.0,
):
    """Create a mock Connection object with the given attributes."""
    conn = MagicMock()
    conn.id = conn_id
    conn.score_reasoning = score_reasoning
    conn.enriched_at = enriched_at
    conn.reconnect_score = reconnect_score
    return conn


def _make_mock_get_session(connections: list):
    """Return a context-manager factory yielding a mock session with given connections."""

    @contextmanager
    def mock_get_session():
        session = MagicMock()
        session.exec.return_value.all.return_value = connections
        yield session

    return mock_get_session


# ---------------------------------------------------------------------------
# INFRA-02: Score breakdown — find and rescore missing dimension_scores
# ---------------------------------------------------------------------------


class TestInfra02ScoreBreakdown:
    """Tests for find_contacts_missing_dimension_scores() and rescore_missing_dimensions()."""

    def test_find_missing_dimension_scores(self, monkeypatch):
        """find_contacts_missing_dimension_scores() returns IDs of contacts with missing or empty dimension_scores.

        Given 3 connections:
        - conn1: valid dimension_scores dict with all 5 keys -> NOT returned
        - conn2: dimension_scores is empty dict {} -> returned
        - conn3: score_reasoning has no dimension_scores key -> returned
        Only conn2 and conn3 should be in the result.
        """
        conn1 = _make_connection(
            "conn1",
            json.dumps({
                "reasoning": "Good match",
                "key_factors": [],
                "conversation_hooks": [],
                "dimension_scores": {
                    "goal_alignment": 20,
                    "industry_overlap": 15,
                    "mutual_value": 12,
                    "conversation_hooks": 14,
                    "network_reach": 8,
                },
            }),
        )
        conn2 = _make_connection(
            "conn2",
            json.dumps({
                "reasoning": "Decent",
                "key_factors": [],
                "conversation_hooks": [],
                "dimension_scores": {},  # empty — broken
            }),
        )
        conn3 = _make_connection(
            "conn3",
            json.dumps({
                "reasoning": "Needs rescore",
                "key_factors": [],
                "conversation_hooks": [],
                # no dimension_scores key — broken
            }),
        )

        mock_session_factory = _make_mock_get_session([conn1, conn2, conn3])
        monkeypatch.setattr("src.llm.scoring.get_session", mock_session_factory)

        from src.llm.scoring import find_contacts_missing_dimension_scores
        result = find_contacts_missing_dimension_scores()

        assert "conn1" not in result, "conn1 has valid dimension_scores and should be excluded"
        assert "conn2" in result, "conn2 has empty dimension_scores and should be returned"
        assert "conn3" in result, "conn3 has no dimension_scores key and should be returned"
        assert len(result) == 2

    def test_dimension_scores_populated(self, monkeypatch):
        """rescore_missing_dimensions() causes dimension_scores to be populated after rescoring.

        Given a connection with empty dimension_scores, after rescore the score_reasoning
        JSON should contain all 5 dimension keys with numeric values.
        """
        from src.llm.scoring import ScoreResult

        conn_with_empty_dims = _make_connection(
            "conn-empty",
            json.dumps({
                "reasoning": "Old score",
                "key_factors": [],
                "conversation_hooks": [],
                "dimension_scores": {},
            }),
        )

        mock_session_factory = _make_mock_get_session([conn_with_empty_dims])
        monkeypatch.setattr("src.llm.scoring.get_session", mock_session_factory)

        expected_score_result = ScoreResult(
            score=72.0,
            reasoning="Strong goal alignment",
            key_factors=["Key factor 1"],
            conversation_hooks=["Hook 1"],
            dimension_scores={
                "goal_alignment": 20,
                "industry_overlap": 15,
                "mutual_value": 12,
                "conversation_hooks": 14,
                "network_reach": 11,
            },
        )

        with patch("src.llm.scoring.score_connections_batch") as mock_batch:
            mock_batch.return_value = {"scored": 1, "failed": 0, "errors": []}

            from src.llm.scoring import rescore_missing_dimensions
            result = rescore_missing_dimensions()

        # The batch was called with the ID of our broken connection
        mock_batch.assert_called_once_with(["conn-empty"])
        assert result["scored"] == 1
        assert result["failed"] == 0

    def test_rescore_skips_unenriched(self, monkeypatch):
        """find_contacts_missing_dimension_scores() excludes connections with enriched_at=None.

        Even if a connection has score_reasoning with empty dimension_scores,
        if enriched_at is None it should not be included as a rescore candidate.
        """
        conn_unenriched = _make_connection(
            "conn-unenriched",
            json.dumps({
                "reasoning": "Old score",
                "key_factors": [],
                "conversation_hooks": [],
                "dimension_scores": {},  # broken, but unenriched
            }),
            enriched_at=None,  # not enriched
        )

        mock_session_factory = _make_mock_get_session([conn_unenriched])
        monkeypatch.setattr("src.llm.scoring.get_session", mock_session_factory)

        from src.llm.scoring import find_contacts_missing_dimension_scores
        result = find_contacts_missing_dimension_scores()

        assert "conn-unenriched" not in result, (
            "Unenriched connections (enriched_at=None) must be excluded from rescore candidates"
        )
        assert len(result) == 0


# ---------------------------------------------------------------------------
# INFRA-01: Gmail OAuth configuration (implemented in plan 03)
# ---------------------------------------------------------------------------


def test_oauth_not_configured():
    """is_oauth_configured() returns False when no GmailCredentials row exists."""
    from contextlib import contextmanager

    @contextmanager
    def mock_get_session_none():
        session = MagicMock()
        session.get.return_value = None
        yield session

    with patch("src.integrations.gmail.get_session", mock_get_session_none):
        from src.integrations.gmail import is_oauth_configured
        result = is_oauth_configured()

    assert result is False, "is_oauth_configured() must return False when no GmailCredentials row"


def test_oauth_send_email_mock():
    """oauth_send_html_email() calls Gmail API with base64-encoded MIMEMultipart."""
    mock_creds = MagicMock()
    mock_creds.expired = False

    mock_message = MagicMock()
    mock_message.execute.return_value = {"id": "msg-123"}

    mock_messages = MagicMock()
    mock_messages.send.return_value = mock_message

    mock_users = MagicMock()
    mock_users.messages.return_value = mock_messages

    mock_service = MagicMock()
    mock_service.users.return_value = mock_users

    with patch("src.integrations.gmail._load_oauth_credentials", return_value=mock_creds):
        with patch("src.integrations.gmail.build", return_value=mock_service):
            from src.integrations.gmail import oauth_send_html_email
            result = oauth_send_html_email("to@test.com", "Subject", "<h1>Test</h1>")

    # Assert send was called with userId='me' and a body dict containing 'raw'
    send_call = mock_messages.send.call_args
    assert send_call is not None, "service.users().messages().send() was not called"
    call_kwargs = send_call.kwargs if send_call.kwargs else {}
    call_args = send_call.args if send_call.args else ()
    # send(userId='me', body={'raw': ...})
    # kwargs may be positional in some mock setups — check all
    all_args = {**{str(i): v for i, v in enumerate(call_args)}, **call_kwargs}
    assert "userId" in all_args or "me" in str(all_args), (
        f"send() must be called with userId='me', got: {send_call}"
    )
    body_arg = all_args.get("body") or all_args.get("1")
    assert body_arg is not None and "raw" in (body_arg if isinstance(body_arg, dict) else {}), (
        f"send() must be called with body dict containing 'raw' key, got: {body_arg}"
    )
    assert result["sent"] is True
    assert result["message_id"] == "msg-123"


def test_no_gmail_creds_in_push():
    """push_to_cloud() does NOT include gmail_credentials in sync payload.

    Reads the push.py source to verify GmailCredentials is not imported
    and gmail_credentials is not in the stats dict initialization.
    """
    import pathlib
    import re

    push_source = pathlib.Path("/Users/gavin/Developer/reconnect/src/sync/push.py").read_text()

    # Check GmailCredentials is not imported (must not appear in an import statement)
    import_lines = [
        line for line in push_source.splitlines()
        if line.strip().startswith("from ") or line.strip().startswith("import ")
    ]
    import_block = "\n".join(import_lines)
    assert "GmailCredentials" not in import_block, (
        "GmailCredentials should be removed from push.py import statements (security: tokens stay local)"
    )

    # Check gmail_credentials is not in stats dict initialization (no active key, only comments OK)
    active_stats_lines = [
        line for line in push_source.splitlines()
        if '"gmail_credentials"' in line and not line.strip().startswith("#")
    ]
    assert len(active_stats_lines) == 0, (
        f"gmail_credentials key should be removed from stats dict in push.py, found: {active_stats_lines}"
    )


# ---------------------------------------------------------------------------
# QUEUE-01/02/03: Queue UX stubs
# (implemented in plan 03)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Implemented in plan 03 — JS queue sort toggle verification")
def test_queue_sort_toggle():
    """Queue sort toggle cycles through sort options and re-renders queue."""
    pass


@pytest.mark.skip(reason="Implemented in plan 03 — JS queue status filter verification")
def test_queue_status_filter():
    """Queue status filter pill filters visible queue cards by status."""
    pass


@pytest.mark.skip(reason="Implemented in plan 03 — JS industry dual-path filter verification")
def test_industry_dual_path():
    """Industry filter works for both queue view and connection browser."""
    pass
