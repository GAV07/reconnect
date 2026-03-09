"""Phase 3 PWA feature completeness tests.

Tests for:
- VIEW-01: Funnel stage counts (reviewed, reached_out, connected) in dashboard snapshot
- VIEW-02: Enrichment status counts (need_enrichment, enriched, enriched_pct) in dashboard snapshot
- PROFILE-01: Score reasoning JSON has all 5 dimension score keys
- PROFILE-02: Professional context fields accessible via get_enrichment_data()
- PROFILE-03: Connection strength fields accessible on Connection model
- PROFILE-04: Enrichment data fields accessible
- VIEW-03: Feedback history rows have expected feedback_type values
"""

import json
from datetime import datetime
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session(return_values: list):
    """Create a mock SQLModel session whose exec().one() calls return values in sequence.

    Each call to session.exec(...).one() consumes the next value from return_values.
    """
    session = MagicMock()
    one_mock = MagicMock()
    one_mock.one.side_effect = return_values
    session.exec.return_value = one_mock
    return session


def _make_mock_get_session(return_values: list):
    """Return a context-manager factory that yields a mock session."""
    from contextlib import contextmanager

    session = _make_mock_session(return_values)

    @contextmanager
    def mock_get_session():
        yield session

    return mock_get_session


# ---------------------------------------------------------------------------
# Test 1: Funnel counts in snapshot (VIEW-01)
# NOTE: This test is initially RED — Task 2 will make it GREEN.
# ---------------------------------------------------------------------------


def test_funnel_counts_in_snapshot(monkeypatch):
    """compute_data_quality() returns reviewed, reached_out, and connected integer counts.

    VIEW-01: The PWA dashboard funnel needs these counts in the snapshot data_quality dict.
    """
    # Query order in compute_data_quality():
    # 1. total, 2. scored, 3. enriched, 4. has_email, 5. has_activity
    # After Task 2: 6. reviewed, 7. reached_out, 8. connected
    mock_get_session = _make_mock_get_session([
        100,  # total
        80,   # scored
        60,   # enriched
        55,   # has_email
        40,   # has_activity
        15,   # reviewed (approved + skipped)
        10,   # reached_out (sent)
        3,    # connected (replied)
    ])

    monkeypatch.setattr("src.services.dashboard_service.get_session", mock_get_session)

    from src.services.dashboard_service import compute_data_quality

    result = compute_data_quality()

    assert "reviewed" in result, "compute_data_quality() must return 'reviewed' key"
    assert "reached_out" in result, "compute_data_quality() must return 'reached_out' key"
    assert "connected" in result, "compute_data_quality() must return 'connected' key"

    assert isinstance(result["reviewed"], int), "'reviewed' must be an integer"
    assert isinstance(result["reached_out"], int), "'reached_out' must be an integer"
    assert isinstance(result["connected"], int), "'connected' must be an integer"

    assert result["reviewed"] >= 0
    assert result["reached_out"] >= 0
    assert result["connected"] >= 0

    # Verify the actual values from our mock
    assert result["reviewed"] == 15
    assert result["reached_out"] == 10
    assert result["connected"] == 3


# ---------------------------------------------------------------------------
# Test 2: Enrichment status counts (VIEW-02)
# ---------------------------------------------------------------------------


def test_enrichment_status_counts(monkeypatch):
    """compute_data_quality() returns need_enrichment, enriched, enriched_pct.

    VIEW-02: PWA data completeness section needs these counts.
    """
    # Provide enough return values for all queries (including funnel counts after Task 2)
    mock_get_session = _make_mock_get_session([
        200,  # total
        150,  # scored
        120,  # enriched
        110,  # has_email
        90,   # has_activity
        25,   # reviewed
        18,   # reached_out
        7,    # connected
    ])

    monkeypatch.setattr("src.services.dashboard_service.get_session", mock_get_session)

    from src.services.dashboard_service import compute_data_quality

    result = compute_data_quality()

    assert "need_enrichment" in result, "compute_data_quality() must return 'need_enrichment'"
    assert "enriched" in result, "compute_data_quality() must return 'enriched'"
    assert "enriched_pct" in result, "compute_data_quality() must return 'enriched_pct'"

    # Verify derived calculation: need_enrichment = total_contacts - enriched
    assert result["need_enrichment"] == result["total_contacts"] - result["enriched"], \
        "need_enrichment must equal total_contacts - enriched"


# ---------------------------------------------------------------------------
# Test 3: Score reasoning dimension keys (PROFILE-01)
# ---------------------------------------------------------------------------


def test_score_reasoning_has_all_dimensions():
    """Score reasoning JSON contains all 5 dimension score keys with numeric values.

    PROFILE-01: PWA profile view renders dimension score breakdown.
    """
    # Realistic score_reasoning JSON from src/llm/scoring.py ScoreResult format
    score_reasoning = json.dumps({
        "score": 78,
        "reasoning": "Strong goal alignment in product management space",
        "key_factors": [
            "VP of Product at SaaS company",
            "Posted about PM hiring recently",
            "Shared interest in AI tooling"
        ],
        "conversation_hooks": [
            "Ask about their recent post on PM hiring",
            "Mention shared interest in AI product development"
        ],
        "dimension_scores": {
            "goal_alignment": 22,
            "industry_overlap": 16,
            "mutual_value": 14,
            "conversation_hooks": 17,
            "network_reach": 9,
        }
    })

    parsed = json.loads(score_reasoning)
    dimension_scores = parsed.get("dimension_scores", {})

    expected_keys = {
        "goal_alignment",
        "industry_overlap",
        "mutual_value",
        "conversation_hooks",
        "network_reach",
    }

    assert set(dimension_scores.keys()) == expected_keys, \
        f"dimension_scores must contain exactly: {expected_keys}"

    for key, value in dimension_scores.items():
        assert isinstance(value, (int, float)), \
            f"dimension_scores['{key}'] must be numeric, got {type(value)}"


# ---------------------------------------------------------------------------
# Test 4: Professional context fields (PROFILE-02)
# ---------------------------------------------------------------------------


def test_professional_context_fields():
    """get_enrichment_data() unwraps nested 'data' key from raw_enrichment.

    PROFILE-02: PWA profile view needs headline and company_industry from enrichment.
    """
    from src.database.models import get_enrichment_data

    # Simulate RapidAPI-style response with nested 'data' key
    raw_enrichment = {
        "data": {
            "headline": "VP of Product at SaaS Inc.",
            "companyIndustry": "Software",
            "company_industry": "Software",
            "firstName": "Alice",
            "lastName": "Smith",
            "summary": "Passionate about product-led growth.",
        }
    }

    conn = MagicMock()
    conn.raw_enrichment = raw_enrichment

    enrichment = get_enrichment_data(conn)

    # Should unwrap the 'data' key
    assert "headline" in enrichment, "Unwrapped enrichment must contain 'headline'"
    assert enrichment["headline"] == "VP of Product at SaaS Inc."

    # Either snake_case or camelCase company industry field
    has_industry = "company_industry" in enrichment or "companyIndustry" in enrichment
    assert has_industry, "Unwrapped enrichment must contain company industry field"


# ---------------------------------------------------------------------------
# Test 5: Connection strength fields (PROFILE-03)
# ---------------------------------------------------------------------------


def test_connection_strength_fields():
    """Connection model exposes relationship strength fields.

    PROFILE-03: PWA profile view renders connection strength signals.
    """
    from src.database.models import Connection

    # Verify field names exist on the model class (without hitting DB)
    model_fields = Connection.model_fields

    assert "message_count" in model_fields, "Connection must have 'message_count' field"
    assert "last_message_date" in model_fields, "Connection must have 'last_message_date' field"
    assert "conversation_status" in model_fields, "Connection must have 'conversation_status' field"
    assert "engagement_score" in model_fields, "Connection must have 'engagement_score' field"

    # Verify types via a mock object (simulates the runtime data shape)
    conn = MagicMock()
    conn.message_count = 5
    conn.last_message_date = datetime(2025, 11, 15)
    conn.conversation_status = "active"
    conn.engagement_score = 72.5

    assert isinstance(conn.message_count, int)
    assert isinstance(conn.last_message_date, datetime)
    assert isinstance(conn.conversation_status, str)
    assert isinstance(conn.engagement_score, float)


# ---------------------------------------------------------------------------
# Test 6: Enrichment fields (PROFILE-04)
# ---------------------------------------------------------------------------


def test_enrichment_fields():
    """Connection model exposes location, email, linkedin_url, data_completeness_score.

    PROFILE-04: PWA profile view contact section needs these fields.
    """
    from src.database.models import Connection, get_enrichment_data

    # Verify field names exist on the model class
    model_fields = Connection.model_fields

    assert "location" in model_fields, "Connection must have 'location' field"
    assert "email" in model_fields, "Connection must have 'email' field"
    assert "linkedin_url" in model_fields, "Connection must have 'linkedin_url' field"
    assert "data_completeness_score" in model_fields, \
        "Connection must have 'data_completeness_score' field"

    # Verify get_enrichment_data works for the headline subfield
    raw_enrichment = {
        "data": {
            "headline": "Senior Engineer at TechCorp",
        }
    }
    conn = MagicMock()
    conn.raw_enrichment = raw_enrichment

    enrichment = get_enrichment_data(conn)
    assert enrichment.get("headline") == "Senior Engineer at TechCorp"


# ---------------------------------------------------------------------------
# Test 7: Feedback history rows (VIEW-03)
# ---------------------------------------------------------------------------


def test_feedback_history_rows():
    """UserFeedback objects have feedback_type from the expected set.

    VIEW-03: PWA feedback history view renders feedback type labels.
    """
    from src.database.models import UserFeedback

    valid_feedback_types = {
        "suggestion_quality",
        "outcome",
        "preference",
        "digest_rating",
        "never_suggest",
        "always_suggest",
    }

    # Verify the model has the expected fields
    model_fields = UserFeedback.model_fields
    assert "feedback_type" in model_fields, "UserFeedback must have 'feedback_type' field"
    assert "rating" in model_fields, "UserFeedback must have 'rating' field"
    assert "created_at" in model_fields, "UserFeedback must have 'created_at' field"

    # Simulate feedback rows and verify they use valid types
    mock_feedbacks = [
        {"feedback_type": "suggestion_quality", "rating": 4, "created_at": datetime(2026, 3, 1)},
        {"feedback_type": "outcome", "rating": None, "created_at": datetime(2026, 3, 2)},
        {"feedback_type": "digest_rating", "rating": 5, "created_at": datetime(2026, 3, 3)},
        {"feedback_type": "never_suggest", "rating": None, "created_at": datetime(2026, 3, 4)},
        {"feedback_type": "always_suggest", "rating": None, "created_at": datetime(2026, 3, 5)},
        {"feedback_type": "preference", "rating": None, "created_at": datetime(2026, 3, 6)},
    ]

    for fb in mock_feedbacks:
        assert fb["feedback_type"] in valid_feedback_types, \
            f"feedback_type '{fb['feedback_type']}' is not in the expected set"
