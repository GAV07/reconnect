"""Phase 5 dashboard intelligence tests.

Tests for:
- DASH-01: compute_health_breakdown() — per-component insights
- DASH-02: compute_industry_distribution() — dual-key extraction, sorted top-10
- DASH-03: compute_role_seniority_mix() — role keywords + seniority tiers
- DASH-04: compute_score_tier_distribution() — High/Medium/Low buckets
- compute_dashboard_snapshot() extended with all 4 new keys
"""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_connection(
    conn_id: str,
    current_role: str | None = None,
    reconnect_score: float | None = None,
    enriched_at: datetime | None = None,
    raw_enrichment: dict | None = None,
    email: str | None = None,
):
    """Create a mock Connection object with the given attributes."""
    conn = MagicMock()
    conn.id = conn_id
    conn.current_role = current_role
    conn.reconnect_score = reconnect_score
    conn.enriched_at = enriched_at
    conn.raw_enrichment = raw_enrichment
    conn.email = email
    return conn


def _make_mock_get_session(connections: list):
    """Return a context-manager factory yielding a mock session with given connections."""

    @contextmanager
    def mock_get_session():
        session = MagicMock()
        session.exec.return_value.all.return_value = connections
        yield session

    return mock_get_session


def _make_mock_get_session_with_one(connections: list, one_values: list):
    """Return a mock session that supports both .all() and .one().

    connections: returned by .all() calls
    one_values: list of values returned by sequential .one() calls
    """

    @contextmanager
    def mock_get_session():
        session = MagicMock()
        session.exec.return_value.all.return_value = connections
        session.exec.return_value.one.side_effect = one_values
        yield session

    return mock_get_session


# ---------------------------------------------------------------------------
# DASH-01: compute_health_breakdown()
# ---------------------------------------------------------------------------


class TestHealthBreakdown:
    """Tests for compute_health_breakdown()."""

    def test_health_breakdown_low_values(self, monkeypatch):
        """compute_health_breakdown() with low component values returns insight strings suggesting improvement.

        All components below their thresholds should produce insight strings that do NOT
        contain "strong" (they should suggest improvement actions).
        """
        mock_health = {
            "score": 30.0,
            "components": {
                "data_completeness": 40.0,
                "enrichment_pct": 30.0,
                "email_coverage_pct": 25.0,
                "activity_score": 10.0,
            },
        }

        with patch("src.services.dashboard_service.compute_network_health", return_value=mock_health):
            from src.services.dashboard_service import compute_health_breakdown

            result = compute_health_breakdown()

        assert "components" in result
        assert "insights" in result

        for comp_name, comp_data in result["components"].items():
            assert "value" in comp_data
            assert "weight" in comp_data
            assert "insight" in comp_data
            # Low values should NOT produce "strong" insights
            assert "strong" not in comp_data["insight"].lower(), (
                f"Component '{comp_name}' has value {comp_data['value']} (low) "
                f"but insight says 'strong': {comp_data['insight']}"
            )

        assert isinstance(result["insights"], list)
        assert len(result["insights"]) > 0

    def test_health_breakdown_high_values(self, monkeypatch):
        """compute_health_breakdown() with all components >= 80 returns "strong" insight strings."""
        mock_health = {
            "score": 88.0,
            "components": {
                "data_completeness": 85.0,
                "enrichment_pct": 82.0,
                "email_coverage_pct": 80.0,
                "activity_score": 90.0,
            },
        }

        with patch("src.services.dashboard_service.compute_network_health", return_value=mock_health):
            from src.services.dashboard_service import compute_health_breakdown

            result = compute_health_breakdown()

        assert "components" in result
        for comp_name, comp_data in result["components"].items():
            assert "strong" in comp_data["insight"].lower(), (
                f"Component '{comp_name}' has high value {comp_data['value']} "
                f"but insight does not say 'strong': {comp_data['insight']}"
            )


# ---------------------------------------------------------------------------
# DASH-02: compute_industry_distribution()
# ---------------------------------------------------------------------------


class TestIndustryDistribution:
    """Tests for compute_industry_distribution()."""

    def test_industry_distribution_sorted(self, monkeypatch):
        """compute_industry_distribution() returns list sorted by count descending, max 10 items."""
        # Create enriched connections with industries
        conns = [
            _make_connection(f"c{i}", enriched_at=datetime(2026, 1, 1),
                             raw_enrichment={"company_industry": "Technology"})
            for i in range(5)
        ] + [
            _make_connection(f"f{i}", enriched_at=datetime(2026, 1, 1),
                             raw_enrichment={"company_industry": "Finance"})
            for i in range(3)
        ] + [
            _make_connection(f"h{i}", enriched_at=datetime(2026, 1, 1),
                             raw_enrichment={"company_industry": "Healthcare"})
            for i in range(2)
        ]

        monkeypatch.setattr(
            "src.services.dashboard_service.get_session",
            _make_mock_get_session(conns),
        )

        from src.services.dashboard_service import compute_industry_distribution

        result = compute_industry_distribution()

        assert isinstance(result, list)
        assert len(result) <= 10

        # Must be sorted descending by count
        counts = [item["count"] for item in result]
        assert counts == sorted(counts, reverse=True), (
            f"Result is not sorted descending by count: {counts}"
        )

        # Each item must have the required keys
        for item in result:
            assert "industry" in item
            assert "count" in item
            assert "pct" in item

        # Top result should be Technology (5 contacts)
        assert result[0]["industry"] == "Technology"
        assert result[0]["count"] == 5

    def test_industry_dual_key(self, monkeypatch):
        """compute_industry_distribution() handles both company_industry (RapidAPI) and companyIndustry (Apify) keys."""
        conns = [
            # RapidAPI format
            _make_connection("r1", enriched_at=datetime(2026, 1, 1),
                             raw_enrichment={"company_industry": "Technology"}),
            _make_connection("r2", enriched_at=datetime(2026, 1, 1),
                             raw_enrichment={"company_industry": "Technology"}),
            # Apify format
            _make_connection("a1", enriched_at=datetime(2026, 1, 1),
                             raw_enrichment={"companyIndustry": "Finance"}),
        ]

        monkeypatch.setattr(
            "src.services.dashboard_service.get_session",
            _make_mock_get_session(conns),
        )

        from src.services.dashboard_service import compute_industry_distribution

        result = compute_industry_distribution()

        industries = {item["industry"]: item["count"] for item in result}
        assert "Technology" in industries, "RapidAPI 'company_industry' key not extracted"
        assert industries["Technology"] == 2
        assert "Finance" in industries, "Apify 'companyIndustry' key not extracted"
        assert industries["Finance"] == 1

    def test_industry_no_enriched(self, monkeypatch):
        """compute_industry_distribution() returns empty list when no enriched contacts exist."""
        monkeypatch.setattr(
            "src.services.dashboard_service.get_session",
            _make_mock_get_session([]),
        )

        from src.services.dashboard_service import compute_industry_distribution

        result = compute_industry_distribution()

        assert result == [], f"Expected empty list, got: {result}"


# ---------------------------------------------------------------------------
# DASH-03: compute_role_seniority_mix() and _classify_seniority()
# ---------------------------------------------------------------------------


class TestRoleSeniorityMix:
    """Tests for _classify_seniority() and compute_role_seniority_mix()."""

    def test_seniority_classification(self):
        """_classify_seniority() maps roles correctly to seniority tiers."""
        from src.services.dashboard_service import _classify_seniority

        assert _classify_seniority("CEO") == "Executive", "CEO should be Executive"
        assert _classify_seniority("Senior Engineer") == "Senior", "Senior Engineer should be Senior"
        assert _classify_seniority("Analyst") == "Mid-level", "Analyst should be Mid-level"
        assert _classify_seniority("") == "Unknown", "Empty string should be Unknown"
        assert _classify_seniority(None) == "Unknown", "None should be Unknown"

    def test_role_seniority_structure(self, monkeypatch):
        """compute_role_seniority_mix() returns dict with 'roles' and 'seniority' keys."""
        conns = [
            _make_connection("c1", current_role="Software Engineer"),
            _make_connection("c2", current_role="Product Manager"),
            _make_connection("c3", current_role="Senior Director of Engineering"),
            _make_connection("c4", current_role="CEO"),
        ]

        monkeypatch.setattr(
            "src.services.dashboard_service.get_session",
            _make_mock_get_session(conns),
        )

        from src.services.dashboard_service import compute_role_seniority_mix

        result = compute_role_seniority_mix()

        assert "roles" in result, "Result must have 'roles' key"
        assert "seniority" in result, "Result must have 'seniority' key"
        assert isinstance(result["roles"], list), "'roles' must be a list"
        assert isinstance(result["seniority"], list), "'seniority' must be a list"

        # Each role item must have keyword and count
        for item in result["roles"]:
            assert "keyword" in item
            assert "count" in item

        # Each seniority item must have tier and count
        for item in result["seniority"]:
            assert "tier" in item
            assert "count" in item

        # Seniority tiers present
        tiers = {item["tier"] for item in result["seniority"]}
        # At least some tiers should be present given our input data
        assert len(tiers) > 0, "No seniority tiers found"


# ---------------------------------------------------------------------------
# DASH-04: compute_score_tier_distribution()
# ---------------------------------------------------------------------------


class TestScoreTierDistribution:
    """Tests for compute_score_tier_distribution()."""

    def test_score_tier_buckets(self, monkeypatch):
        """compute_score_tier_distribution() correctly buckets scores into High/Medium/Low."""
        conns = [
            _make_connection("h1", reconnect_score=75.0),  # High (>=70)
            _make_connection("m1", reconnect_score=55.0),  # Medium (>=40, <70)
            _make_connection("l1", reconnect_score=25.0),  # Low (<40)
        ]

        monkeypatch.setattr(
            "src.services.dashboard_service.get_session",
            _make_mock_get_session(conns),
        )

        from src.services.dashboard_service import compute_score_tier_distribution

        result = compute_score_tier_distribution()

        tiers_by_name = {item["tier"]: item for item in result}

        assert any("High" in tier for tier in tiers_by_name), "High tier not found"
        assert any("Medium" in tier for tier in tiers_by_name), "Medium tier not found"
        assert any("Low" in tier for tier in tiers_by_name), "Low tier not found"

        high_item = next(item for item in result if "High" in item["tier"])
        medium_item = next(item for item in result if "Medium" in item["tier"])
        low_item = next(item for item in result if "Low" in item["tier"])

        assert high_item["count"] == 1, f"Expected 1 High, got {high_item['count']}"
        assert medium_item["count"] == 1, f"Expected 1 Medium, got {medium_item['count']}"
        assert low_item["count"] == 1, f"Expected 1 Low, got {low_item['count']}"

    def test_score_tier_excludes_unscored(self, monkeypatch):
        """compute_score_tier_distribution() excludes contacts with reconnect_score=None."""
        conns = [
            _make_connection("h1", reconnect_score=75.0),
            _make_connection("u1", reconnect_score=None),  # unscored — must be excluded
            _make_connection("u2", reconnect_score=None),  # unscored — must be excluded
        ]

        monkeypatch.setattr(
            "src.services.dashboard_service.get_session",
            _make_mock_get_session(conns),
        )

        from src.services.dashboard_service import compute_score_tier_distribution

        result = compute_score_tier_distribution()

        total_count = sum(item["count"] for item in result)
        assert total_count == 1, (
            f"Should only count 1 scored contact, got {total_count} "
            f"(unscored contacts must be excluded)"
        )

    def test_score_tier_pct_sums(self, monkeypatch):
        """Tier percentages sum to 100% (within 0.5% tolerance)."""
        conns = [
            _make_connection("h1", reconnect_score=80.0),
            _make_connection("h2", reconnect_score=75.0),
            _make_connection("m1", reconnect_score=60.0),
            _make_connection("m2", reconnect_score=50.0),
            _make_connection("m3", reconnect_score=45.0),
            _make_connection("l1", reconnect_score=30.0),
            _make_connection("l2", reconnect_score=20.0),
        ]

        monkeypatch.setattr(
            "src.services.dashboard_service.get_session",
            _make_mock_get_session(conns),
        )

        from src.services.dashboard_service import compute_score_tier_distribution

        result = compute_score_tier_distribution()

        total_pct = sum(item["pct"] for item in result)
        assert abs(total_pct - 100.0) <= 0.5, (
            f"Tier percentages should sum to ~100% (tolerance 0.5%), got {total_pct}"
        )


# ---------------------------------------------------------------------------
# compute_dashboard_snapshot() — extended with 4 new keys
# ---------------------------------------------------------------------------


class TestDashboardSnapshot:
    """Tests for compute_dashboard_snapshot() Phase 5 extension."""

    def test_snapshot_includes_new_keys(self, monkeypatch):
        """compute_dashboard_snapshot() dict has all 4 new Phase 5 keys."""
        # Patch all compute functions to return simple values
        monkeypatch.setattr(
            "src.services.dashboard_service.compute_network_health",
            lambda: {"score": 70.0, "components": {}},
        )
        monkeypatch.setattr(
            "src.services.dashboard_service.compute_opportunity_alerts",
            lambda: [],
        )
        monkeypatch.setattr(
            "src.services.dashboard_service.compute_feedback_insights",
            lambda: {},
        )
        monkeypatch.setattr(
            "src.services.dashboard_service.compute_data_quality",
            lambda: {},
        )
        monkeypatch.setattr(
            "src.services.dashboard_service.compute_health_breakdown",
            lambda: {"components": {}, "insights": []},
        )
        monkeypatch.setattr(
            "src.services.dashboard_service.compute_industry_distribution",
            lambda: [],
        )
        monkeypatch.setattr(
            "src.services.dashboard_service.compute_role_seniority_mix",
            lambda: {"roles": [], "seniority": []},
        )
        monkeypatch.setattr(
            "src.services.dashboard_service.compute_score_tier_distribution",
            lambda: [],
        )

        from src.services.dashboard_service import compute_dashboard_snapshot

        result = compute_dashboard_snapshot()

        assert "health_breakdown" in result, "Snapshot must include 'health_breakdown' (DASH-01)"
        assert "industry_distribution" in result, "Snapshot must include 'industry_distribution' (DASH-02)"
        assert "role_seniority_mix" in result, "Snapshot must include 'role_seniority_mix' (DASH-03)"
        assert "score_tier_distribution" in result, "Snapshot must include 'score_tier_distribution' (DASH-04)"

        # Existing keys must still be present
        assert "network_health" in result
        assert "computed_at" in result
