"""Phase 12 enrichment extraction tests.

Tests for:
- ENRICH-01: get_enrichment_coverage() — field-level coverage stats
- ENRICH-02: education_text extraction — education_text matches enriched_school
- ENRICH-03: 7-field extraction at enrichment time (extract_enrichment_fields)
- ENRICH-04: idempotent backfill (backfill_enrichment_fields)
"""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from src.database.models import Connection, get_enrichment_data
from src.pipeline.enrichment_extractor import (
    _clean_headline,
    _normalize_industry,
    backfill_enrichment_fields,
    extract_enrichment_fields,
    get_enrichment_coverage,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_session(test_engine):
    """Create a test session."""
    with Session(test_engine) as session:
        yield session


def _make_connection(name="Test User", raw_enrichment=None, **kwargs):
    """Helper to create a Connection with enrichment data."""
    return Connection(
        name=name,
        raw_enrichment=raw_enrichment,
        enriched_at=datetime.utcnow() if raw_enrichment else None,
        **kwargs,
    )


def _make_fake_get_session(engine):
    """Return a context manager factory that uses the test engine."""

    @contextmanager
    def fake_get_session():
        with Session(engine) as s:
            yield s
            s.commit()

    return fake_get_session


MOCK_ENRICHMENT = {
    "headline": "Senior Product Manager | AI Enthusiast",
    "job_title": "Senior Product Manager",
    "company": "Acme Corp",
    "company_industry": "Computer Software",
    "city": "san francisco",
    "country": "united states",
    "educations": [
        {"school": "Stanford University", "degree": "MBA"},
        {"school": "UC Berkeley", "degree": "BS"},
    ],
}


# ---------------------------------------------------------------------------
# TestFieldExtraction — extract_enrichment_fields() unit tests
# ---------------------------------------------------------------------------


class TestFieldExtraction:
    """Unit tests for extract_enrichment_fields() — ENRICH-03."""

    def test_industry_extracted_with_normalization(self, test_engine):
        """extract_enrichment_fields sets enriched_industry='Technology' from company_industry='Computer Software'."""
        conn = _make_connection()
        data = {"company_industry": "Computer Software"}
        extract_enrichment_fields(conn, data, overwrite=True)
        assert conn.enriched_industry == "Technology"

    def test_industry_dual_key_apify(self, test_engine):
        """extract_enrichment_fields sets enriched_industry from companyIndustry key (Apify format)."""
        conn = _make_connection()
        data = {"companyIndustry": "Financial Services"}
        extract_enrichment_fields(conn, data, overwrite=True)
        assert conn.enriched_industry == "Finance"

    def test_headline_extracted_cleaned(self):
        """extract_enrichment_fields sets enriched_headline with emoji stripped."""
        conn = _make_connection()
        data = {"headline": "Senior PM \U0001F680 | Building AI products"}
        extract_enrichment_fields(conn, data, overwrite=True)
        assert conn.enriched_headline is not None
        # Rocket emoji should be stripped
        assert "\U0001F680" not in conn.enriched_headline
        assert "Senior PM" in conn.enriched_headline

    def test_city_country_title_cased(self):
        """extract_enrichment_fields sets enriched_city='San Francisco' from 'san francisco'."""
        conn = _make_connection()
        data = {"city": "san francisco", "country": "united states"}
        extract_enrichment_fields(conn, data, overwrite=True)
        assert conn.enriched_city == "San Francisco"
        assert conn.enriched_country == "United States"

    def test_school_concatenated(self):
        """extract_enrichment_fields sets enriched_school='Stanford University, UC Berkeley' from 2-school educations array."""
        conn = _make_connection()
        data = {
            "educations": [
                {"school": "Stanford University", "degree": "MBA"},
                {"school": "UC Berkeley", "degree": "BS"},
            ]
        }
        extract_enrichment_fields(conn, data, overwrite=True)
        assert conn.enriched_school == "Stanford University, UC Berkeley"

    def test_education_text_matches_school(self):
        """education_text value equals enriched_school value (school names only)."""
        conn = _make_connection()
        data = {
            "educations": [
                {"school": "Stanford University", "degree": "MBA"},
                {"school": "UC Berkeley", "degree": "BS"},
            ]
        }
        extract_enrichment_fields(conn, data, overwrite=True)
        assert conn.education_text == conn.enriched_school

    def test_seniority_classified(self):
        """extract_enrichment_fields sets enriched_seniority='Senior' for current_role='Senior Product Manager'."""
        conn = _make_connection(current_role="Senior Product Manager")
        data = {}  # seniority uses connection.current_role
        extract_enrichment_fields(conn, data, overwrite=True)
        assert conn.enriched_seniority == "Senior"

    def test_overwrite_false_skips_existing(self):
        """With overwrite=False, pre-existing non-NULL values are not overwritten."""
        conn = _make_connection(
            enriched_industry="Finance",
            enriched_city="New York",
        )
        data = {
            "company_industry": "Computer Software",
            "city": "san francisco",
        }
        extract_enrichment_fields(conn, data, overwrite=False)
        # Pre-existing values should be preserved
        assert conn.enriched_industry == "Finance"
        assert conn.enriched_city == "New York"

    def test_overwrite_true_replaces_existing(self):
        """With overwrite=True, pre-existing values are replaced."""
        conn = _make_connection(
            enriched_industry="Finance",
            enriched_city="New York",
        )
        data = {
            "company_industry": "Computer Software",
            "city": "san francisco",
        }
        extract_enrichment_fields(conn, data, overwrite=True)
        # Values should be replaced
        assert conn.enriched_industry == "Technology"
        assert conn.enriched_city == "San Francisco"

    def test_empty_data_no_crash(self):
        """extract_enrichment_fields({}) on empty dict does not crash and leaves fields as None."""
        conn = _make_connection()
        extract_enrichment_fields(conn, {}, overwrite=True)
        # All enrichment fields remain None — no crash
        assert conn.enriched_industry is None
        assert conn.enriched_headline is None
        assert conn.enriched_city is None
        assert conn.enriched_country is None
        assert conn.enriched_school is None
        assert conn.education_text is None


# ---------------------------------------------------------------------------
# TestBackfill — backfill_enrichment_fields() tests
# ---------------------------------------------------------------------------


class TestBackfill:
    """Tests for backfill_enrichment_fields() — ENRICH-04."""

    def test_backfill_fills_null_columns(self, test_engine):
        """backfill_enrichment_fields populates NULL columns from raw_enrichment."""
        with Session(test_engine) as session:
            conn = _make_connection(
                raw_enrichment={"data": MOCK_ENRICHMENT}
            )
            session.add(conn)
            session.commit()

        with patch("src.database.engine.get_session", _make_fake_get_session(test_engine)):
            result = backfill_enrichment_fields()

        assert result["processed"] >= 1
        # Industry, city, school should all have been filled
        with Session(test_engine) as session:
            conns = session.exec(select(Connection)).all()
            assert len(conns) == 1
            conn = conns[0]
            assert conn.enriched_industry == "Technology"  # "Computer Software" -> "Technology"
            assert conn.enriched_city == "San Francisco"
            assert conn.enriched_school == "Stanford University, UC Berkeley"

    def test_backfill_idempotent(self, test_engine):
        """Running backfill twice returns processed=0 on second run."""
        with Session(test_engine) as session:
            conn = _make_connection(
                raw_enrichment={"data": MOCK_ENRICHMENT}
            )
            session.add(conn)
            session.commit()

        fake_session = _make_fake_get_session(test_engine)

        with patch("src.database.engine.get_session", fake_session):
            first_result = backfill_enrichment_fields()

        assert first_result["processed"] >= 1, "First run should have processed contacts"

        # Second run with the same data — all fields now populated, nothing to backfill
        with patch("src.database.engine.get_session", fake_session):
            second_result = backfill_enrichment_fields()

        assert second_result["processed"] == 0, (
            f"Second run should process 0 contacts (idempotent), got {second_result['processed']}"
        )

    def test_backfill_sets_updated_at(self, test_engine):
        """backfill updates connection.updated_at so push_to_cloud picks up changes."""
        original_updated_at = datetime(2020, 1, 1)
        with Session(test_engine) as session:
            conn = _make_connection(
                raw_enrichment={"data": MOCK_ENRICHMENT}
            )
            conn.updated_at = original_updated_at
            session.add(conn)
            session.commit()
            conn_id = session.exec(select(Connection)).first().id

        with patch("src.database.engine.get_session", _make_fake_get_session(test_engine)):
            result = backfill_enrichment_fields()

        assert result["processed"] >= 1

        with Session(test_engine) as session:
            conn = session.get(Connection, conn_id)
            assert conn.updated_at > original_updated_at, (
                "updated_at should be bumped during backfill so push_to_cloud picks up changes"
            )


# ---------------------------------------------------------------------------
# TestEnrichmentCoverage — get_enrichment_coverage() tests
# ---------------------------------------------------------------------------


class TestEnrichmentCoverage:
    """Tests for get_enrichment_coverage() — ENRICH-01."""

    def test_coverage_zero_enriched(self, test_engine):
        """get_enrichment_coverage returns total_enriched=0 when no contacts enriched."""
        # Empty database — no enriched contacts
        with patch("src.database.engine.get_session", _make_fake_get_session(test_engine)):
            result = get_enrichment_coverage()

        assert result["total_enriched"] == 0
        assert result["industry_pct"] == 0.0
        assert result["education_pct"] == 0.0
        assert result["headline_pct"] == 0.0
        assert result["city_pct"] == 0.0
        assert result["country_pct"] == 0.0

    def test_coverage_calculates_percentages(self, test_engine):
        """get_enrichment_coverage returns correct counts and percentages."""
        with Session(test_engine) as session:
            # 2 enriched contacts with industry, 1 without
            conn1 = _make_connection(
                name="Alice",
                raw_enrichment={"company_industry": "Technology"},
                enriched_industry="Technology",
                enriched_city="San Francisco",
            )
            conn2 = _make_connection(
                name="Bob",
                raw_enrichment={"company_industry": "Finance"},
                enriched_industry="Finance",
                enriched_city="New York",
            )
            # Carol is enriched but has no extracted fields (simulates pre-Phase-12 contact)
            conn3 = _make_connection(
                name="Carol",
                raw_enrichment={"headline": "Some Job"},
                # enriched_at is set by _make_connection when raw_enrichment is truthy
                # but no extracted columns — industry/city/school are None
            )
            session.add(conn1)
            session.add(conn2)
            session.add(conn3)
            session.commit()

        with patch("src.database.engine.get_session", _make_fake_get_session(test_engine)):
            result = get_enrichment_coverage()

        assert result["total_enriched"] == 3
        assert result["industry_count"] == 2
        assert abs(result["industry_pct"] - 66.7) < 0.2, (
            f"Expected industry_pct ~66.7%, got {result['industry_pct']}"
        )
        assert result["city_count"] == 2
        assert abs(result["city_pct"] - 66.7) < 0.2


# ---------------------------------------------------------------------------
# TestNormalization — _normalize_industry() and _clean_headline() unit tests
# ---------------------------------------------------------------------------


class TestNormalization:
    """Unit tests for normalization helpers — ENRICH-03."""

    def test_industry_map_coverage(self):
        """Known LinkedIn industries map to canonical labels."""
        assert _normalize_industry("Computer Software") == "Technology"
        assert _normalize_industry("Information Technology and Services") == "Technology"
        assert _normalize_industry("Financial Services") == "Finance"
        assert _normalize_industry("Hospital & Health Care") == "Healthcare"
        assert _normalize_industry("Management Consulting") == "Consulting"
        assert _normalize_industry("Higher Education") == "Education"
        assert _normalize_industry("Law Practice") == "Legal"

    def test_industry_passthrough(self):
        """Unknown industry stored as title-cased original (not empty, not None)."""
        result = _normalize_industry("Artisanal Cheese Making")
        assert result == "Artisanal Cheese Making"

    def test_clean_headline_strips_emoji(self):
        """headline with emoji returns cleaned text without the emoji."""
        result = _clean_headline("Builder \U0001F680 | Founder")
        assert "\U0001F680" not in result
        assert "Builder" in result
        assert "Founder" in result

    def test_clean_headline_preserves_accents(self):
        """headline with accented characters preserves them after cleaning."""
        result = _clean_headline("Dir\u00e9cteur G\u00e9n\u00e9ral | Strategy")
        # Accented chars must be preserved
        assert "\u00e9" in result
        assert "Strategy" in result
