"""Enrichment field extraction, backfill, and coverage stats.

Promotes 7 fields from raw_enrichment JSON into first-class columns
on the Connection model. Used at enrichment time, for backfill of
existing contacts, and for coverage diagnostics.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.database.models import Connection

# ---------------------------------------------------------------------------
# Industry normalization
# ---------------------------------------------------------------------------

INDUSTRY_MAP = {
    "information technology and services": "Technology",
    "information technology & services": "Technology",
    "computer software": "Technology",
    "internet": "Technology",
    "computer & network security": "Technology",
    "computer networking": "Technology",
    "semiconductors": "Technology",
    "telecommunications": "Technology",
    "financial services": "Finance",
    "investment banking": "Finance",
    "banking": "Finance",
    "insurance": "Finance",
    "venture capital & private equity": "Finance",
    "capital markets": "Finance",
    "investment management": "Finance",
    "accounting": "Finance",
    "hospital & health care": "Healthcare",
    "health, wellness and fitness": "Healthcare",
    "medical devices": "Healthcare",
    "medical practice": "Healthcare",
    "biotechnology": "Healthcare",
    "pharmaceuticals": "Healthcare",
    "consulting": "Consulting",
    "management consulting": "Consulting",
    "marketing and advertising": "Marketing",
    "marketing & advertising": "Marketing",
    "online media": "Media",
    "media production": "Media",
    "entertainment": "Media",
    "broadcast media": "Media",
    "real estate": "Real Estate",
    "commercial real estate": "Real Estate",
    "education management": "Education",
    "higher education": "Education",
    "e-learning": "Education",
    "primary/secondary education": "Education",
    "law practice": "Legal",
    "legal services": "Legal",
    "retail": "Retail",
    "consumer goods": "Retail",
    "automotive": "Manufacturing",
    "mechanical or industrial engineering": "Manufacturing",
    "oil & energy": "Energy",
    "renewables & environment": "Energy",
    "government administration": "Government",
    "nonprofit organization management": "Nonprofit",
    "civic & social organization": "Nonprofit",
}


def _normalize_industry(raw: str) -> str:
    """Normalize verbose LinkedIn industry to short canonical label.
    Falls back to title-cased trimmed original if not in map."""
    normalized = INDUSTRY_MAP.get(raw.strip().lower())
    return normalized if normalized else raw.strip().title()


# ---------------------------------------------------------------------------
# Headline cleaning
# ---------------------------------------------------------------------------

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U0000FE00-\U0000FE0F"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)


def _clean_headline(text: str) -> str:
    """Strip emoji characters from headline, preserve accented chars."""
    cleaned = EMOJI_PATTERN.sub("", text).strip()
    return re.sub(r"\s{2,}", " ", cleaned)


# ---------------------------------------------------------------------------
# Exported function 1: extract_enrichment_fields
# ---------------------------------------------------------------------------


def extract_enrichment_fields(
    connection: "Connection", data: dict, overwrite: bool = False
) -> None:
    """Extract and set 7 enrichment columns from unwrapped raw_enrichment dict.

    Modifies connection in-place. Caller is responsible for session.add() and commit().
    Does NOT make any API calls.

    Args:
        connection: Connection model instance to update
        data: Unwrapped enrichment dict (already passed through get_enrichment_data())
        overwrite: If True, overwrite existing non-NULL values. If False, only set NULL fields.
    """
    from src.services.dashboard_service import _classify_seniority

    # enriched_industry — dual-key pattern (RapidAPI vs Apify)
    industry = data.get("company_industry") or data.get("companyIndustry")
    if industry and (overwrite or connection.enriched_industry is None):
        connection.enriched_industry = _normalize_industry(industry)

    # enriched_headline
    headline = data.get("headline")
    if headline and (overwrite or connection.enriched_headline is None):
        connection.enriched_headline = _clean_headline(headline.strip())

    # enriched_city
    city = data.get("city")
    if city and (overwrite or connection.enriched_city is None):
        connection.enriched_city = city.strip().title()

    # enriched_country
    country = data.get("country")
    if country and (overwrite or connection.enriched_country is None):
        connection.enriched_country = country.strip().title()

    # enriched_school and education_text — from educations array
    educations = data.get("educations") or []
    schools = [
        edu.get("school", "").strip()
        for edu in educations
        if edu.get("school", "").strip()
    ]
    if schools:
        school_text = ", ".join(schools)
        if overwrite or connection.enriched_school is None:
            connection.enriched_school = school_text
        if overwrite or connection.education_text is None:
            connection.education_text = school_text

    # enriched_seniority — from current_role (on connection) or job_title/headline in data
    role = connection.current_role or data.get("job_title") or data.get("headline") or ""
    if role and (overwrite or connection.enriched_seniority is None):
        connection.enriched_seniority = _classify_seniority(role)


# ---------------------------------------------------------------------------
# Exported function 2: backfill_enrichment_fields
# ---------------------------------------------------------------------------


def backfill_enrichment_fields() -> dict:
    """Backfill 7 enrichment columns for contacts with raw_enrichment but NULL extracted fields.

    Idempotent: only fills NULL columns. Does NOT make API calls.
    Sets updated_at so push_to_cloud() picks up changes.

    Returns:
        {"processed": N, "industry": N, "headline": N, "city": N,
         "country": N, "school": N, "seniority": N, "education": N}
    """
    from datetime import datetime

    from sqlalchemy import or_
    from sqlmodel import select

    from src.database.engine import get_session
    from src.database.models import Connection, get_enrichment_data

    stats = {
        "processed": 0,
        "industry": 0,
        "headline": 0,
        "city": 0,
        "country": 0,
        "school": 0,
        "seniority": 0,
        "education": 0,
    }

    with get_session() as session:
        candidates = session.exec(
            select(Connection)
            .where(Connection.enriched_at.isnot(None))
            .where(
                or_(
                    Connection.enriched_industry.is_(None),
                    Connection.enriched_headline.is_(None),
                    Connection.enriched_city.is_(None),
                    Connection.enriched_country.is_(None),
                    Connection.enriched_school.is_(None),
                    Connection.enriched_seniority.is_(None),
                    Connection.education_text.is_(None),
                )
            )
        ).all()

        for conn in candidates:
            data = get_enrichment_data(conn)
            if not data:
                continue

            before = {
                "industry": conn.enriched_industry,
                "headline": conn.enriched_headline,
                "city": conn.enriched_city,
                "country": conn.enriched_country,
                "school": conn.enriched_school,
                "seniority": conn.enriched_seniority,
                "education": conn.education_text,
            }

            extract_enrichment_fields(conn, data, overwrite=False)

            # Track what was newly filled
            if conn.enriched_industry and not before["industry"]:
                stats["industry"] += 1
            if conn.enriched_headline and not before["headline"]:
                stats["headline"] += 1
            if conn.enriched_city and not before["city"]:
                stats["city"] += 1
            if conn.enriched_country and not before["country"]:
                stats["country"] += 1
            if conn.enriched_school and not before["school"]:
                stats["school"] += 1
            if conn.enriched_seniority and not before["seniority"]:
                stats["seniority"] += 1
            if conn.education_text and not before["education"]:
                stats["education"] += 1

            # Update updated_at so push_to_cloud picks up the changes
            conn.updated_at = datetime.utcnow()
            session.add(conn)

            stats["processed"] += 1

    return stats


# ---------------------------------------------------------------------------
# Exported function 3: get_enrichment_coverage
# ---------------------------------------------------------------------------


def get_enrichment_coverage() -> dict:
    """Compute coverage percentages for each enrichment field across enriched contacts.

    Returns:
        {"total_enriched": N, "industry_count": N, "industry_pct": float, ...}
    """
    from sqlmodel import func, select

    from src.database.engine import get_session
    from src.database.models import Connection

    with get_session() as session:
        total_enriched = session.exec(
            select(func.count(Connection.id)).where(Connection.enriched_at.isnot(None))
        ).one()

        if total_enriched == 0:
            return {
                "total_enriched": 0,
                "industry_count": 0,
                "industry_pct": 0.0,
                "education_count": 0,
                "education_pct": 0.0,
                "headline_count": 0,
                "headline_pct": 0.0,
                "city_count": 0,
                "city_pct": 0.0,
                "country_count": 0,
                "country_pct": 0.0,
                "school_count": 0,
                "school_pct": 0.0,
                "seniority_count": 0,
                "seniority_pct": 0.0,
            }

        def _count_non_null(col):
            count = session.exec(
                select(func.count(Connection.id))
                .where(Connection.enriched_at.isnot(None))
                .where(col.isnot(None))
                .where(col != "")
            ).one()
            return count, round(count / total_enriched * 100, 1)

        industry_count, industry_pct = _count_non_null(Connection.enriched_industry)
        education_count, education_pct = _count_non_null(Connection.education_text)
        headline_count, headline_pct = _count_non_null(Connection.enriched_headline)
        city_count, city_pct = _count_non_null(Connection.enriched_city)
        country_count, country_pct = _count_non_null(Connection.enriched_country)
        school_count, school_pct = _count_non_null(Connection.enriched_school)
        seniority_count, seniority_pct = _count_non_null(Connection.enriched_seniority)

    return {
        "total_enriched": total_enriched,
        "industry_count": industry_count,
        "industry_pct": industry_pct,
        "education_count": education_count,
        "education_pct": education_pct,
        "headline_count": headline_count,
        "headline_pct": headline_pct,
        "city_count": city_count,
        "city_pct": city_pct,
        "country_count": country_count,
        "country_pct": country_pct,
        "school_count": school_count,
        "school_pct": school_pct,
        "seniority_count": seniority_count,
        "seniority_pct": seniority_pct,
    }
