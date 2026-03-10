"""Dashboard computation service — shared by pipeline and PWA.

Computes network health, opportunity alerts, feedback insights, and
data quality metrics. Pipeline pushes results to Supabase as a
DashboardSnapshot for the PWA to read.
"""

import json
import logging
from collections import Counter
from datetime import datetime, timedelta

from sqlmodel import func, select

from src.database.engine import get_session
from src.database.models import (
    Connection,
    DashboardSnapshot,
    OutreachLog,
    OutreachQueueItem,
    UserFeedback,
    UserPreference,
    get_enrichment_data,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seniority classification constants (authoritative keyword lists)
# Source: derived from src/ui/views/dashboard.py role keyword pattern
# ---------------------------------------------------------------------------

EXECUTIVE_KEYWORDS = ["ceo", "cto", "coo", "cfo", "founder", "president", "owner", "partner"]
SENIOR_KEYWORDS = ["vp", "vice president", "director", "head of", "senior", "lead", "staff", "principal", "chief"]
MID_KEYWORDS = ["manager", "analyst", "specialist", "consultant", "engineer", "developer", "designer", "product"]


def _classify_seniority(role: str) -> str:
    """Classify a role title into a seniority tier.

    Order matters: executive first, then senior, then mid-level.
    This intentional priority handles cases like "Senior Director" (executive via
    "director" takes precedence) and "Principal Engineer" (senior via "principal").
    This is approximate classification for directional insight, not HR taxonomy.
    """
    role_lower = (role or "").lower()
    if any(kw in role_lower for kw in EXECUTIVE_KEYWORDS):
        return "Executive"
    if any(kw in role_lower for kw in SENIOR_KEYWORDS):
        return "Senior"
    if any(kw in role_lower for kw in MID_KEYWORDS):
        return "Mid-level"
    return "Unknown"


def _generate_component_insight(component: str, value: float) -> str:
    """Return actionable insight text for a health score component.

    Source: Pattern 4 from 05-RESEARCH.md — 4 components, 3 threshold tiers each.
    """
    if component == "data_completeness":
        if value >= 80:
            return "Data completeness is strong"
        if value >= 60:
            return f"Data completeness is {value:.0f}% — enrich more contacts to improve"
        return f"Data completeness is low ({value:.0f}%) — enriching contacts is your biggest lever"

    if component == "enrichment_pct":
        if value >= 70:
            return "Enrichment rate is strong"
        return f"Only {value:.0f}% of contacts enriched — run the pipeline to enrich more"

    if component == "email_coverage_pct":
        if value >= 70:
            return "Email coverage is strong"
        if value >= 50:
            return "Email coverage is healthy"
        return f"Email coverage is {value:.0f}% — run Hunter.io to find missing email addresses"

    if component == "activity_score":
        if value >= 70:
            return "Network activity is strong"
        if value >= 30:
            return "Moderate activity — keep reaching out"
        return "Low activity — approve more contacts in the queue to build momentum"

    return ""


def compute_network_health() -> dict:
    """Compute composite network health score (0-100).

    Components:
    - Data completeness coverage (avg of all scored contacts)
    - Enrichment % (enriched / total scored)
    - Email coverage (have email / total scored)
    - Activity level (messages sent in last 30 days)
    """
    with get_session() as session:
        total_scored = session.exec(
            select(func.count(Connection.id))
            .where(Connection.reconnect_score.isnot(None))
        ).one()

        if total_scored == 0:
            return {"score": 0, "components": {}}

        # Data completeness
        avg_completeness = session.exec(
            select(func.avg(Connection.data_completeness_score))
            .where(Connection.data_completeness_score.isnot(None))
        ).one() or 0

        # Enrichment coverage
        enriched = session.exec(
            select(func.count(Connection.id))
            .where(Connection.enriched_at.isnot(None))
        ).one()
        enrichment_pct = (enriched / total_scored * 100) if total_scored > 0 else 0

        # Email coverage
        has_email = session.exec(
            select(func.count(Connection.id))
            .where(Connection.reconnect_score.isnot(None))
            .where(Connection.email.isnot(None))
            .where(Connection.email != "")
        ).one()
        email_pct = (has_email / total_scored * 100) if total_scored > 0 else 0

        # Activity (messages sent in last 30 days)
        cutoff_30d = datetime.utcnow() - timedelta(days=30)
        sent_count = session.exec(
            select(func.count(OutreachQueueItem.id))
            .where(OutreachQueueItem.status == "sent")
            .where(OutreachQueueItem.sent_at >= cutoff_30d)
        ).one()
        # Normalize: 10+ messages = 100 activity score
        activity_score = min(sent_count * 10, 100)

    # Weighted composite
    score = (
        avg_completeness * 0.3
        + enrichment_pct * 0.25
        + email_pct * 0.25
        + activity_score * 0.2
    )

    return {
        "score": round(score, 1),
        "components": {
            "data_completeness": round(avg_completeness, 1),
            "enrichment_pct": round(enrichment_pct, 1),
            "email_coverage_pct": round(email_pct, 1),
            "activity_score": activity_score,
        },
    }


def compute_opportunity_alerts() -> list[dict]:
    """Find recent job changes, active posters, stale high-value connections."""
    alerts = []

    with get_session() as session:
        scored = session.exec(
            select(Connection)
            .where(Connection.reconnect_score.isnot(None))
            .where(Connection.reconnect_score >= 50)
            .order_by(Connection.reconnect_score.desc())
            .limit(100)
        ).all()

        for conn in scored:
            enrichment = get_enrichment_data(conn)

            # Recent job change
            join_year = enrichment.get("current_company_join_year")
            join_month = enrichment.get("current_company_join_month")
            if join_year and join_month:
                try:
                    job_start = datetime(int(join_year), int(join_month), 1)
                    months = (datetime.utcnow() - job_start).days / 30
                    if months < 6:
                        alerts.append({
                            "type": "job_change",
                            "connection_id": conn.id,
                            "name": conn.name,
                            "detail": f"Started at {conn.current_company} {months:.0f} months ago",
                            "score": conn.reconnect_score,
                        })
                except (ValueError, TypeError):
                    pass

            # Active poster
            if conn.activity_log and len(conn.activity_log) >= 3:
                alerts.append({
                    "type": "active_poster",
                    "connection_id": conn.id,
                    "name": conn.name,
                    "detail": f"{len(conn.activity_log)} recent posts",
                    "score": conn.reconnect_score,
                })

            # Stale high-value (score >=70, no contact in 90+ days)
            if conn.reconnect_score and conn.reconnect_score >= 70:
                last_contact = conn.last_contacted_at or conn.last_message_date
                if last_contact:
                    days = (datetime.utcnow() - last_contact).days
                    if days > 90:
                        alerts.append({
                            "type": "stale_high_value",
                            "connection_id": conn.id,
                            "name": conn.name,
                            "detail": f"Score {conn.reconnect_score:.0f}, last contact {days} days ago",
                            "score": conn.reconnect_score,
                        })

    # Sort by score descending and limit
    alerts.sort(key=lambda a: a.get("score", 0), reverse=True)
    return alerts[:20]


def compute_feedback_insights() -> dict:
    """Analyze user feedback for preferences and patterns."""
    insights = {
        "preferred_industries": [],
        "skip_patterns": [],
        "outcome_rates": {},
        "avg_digest_rating": None,
    }

    with get_session() as session:
        # Digest ratings
        ratings = session.exec(
            select(UserFeedback.rating)
            .where(UserFeedback.feedback_type == "digest_rating")
            .where(UserFeedback.rating.isnot(None))
            .order_by(UserFeedback.created_at.desc())
            .limit(30)
        ).all()

        if ratings:
            avg = sum(r for (r,) in ratings) / len(ratings)
            insights["avg_digest_rating"] = round(avg, 1)

        # Scoring weight preferences (what the system has learned)
        weight_prefs = session.exec(
            select(UserPreference)
            .where(UserPreference.pref_type == "scoring_weight")
            .where(UserPreference.is_active == True)
        ).all()

        scoring_adjustments = {}
        for pref in weight_prefs:
            try:
                scoring_adjustments[pref.pref_key] = float(pref.pref_value)
            except (ValueError, TypeError):
                pass
        insights["scoring_adjustments"] = scoring_adjustments

    return insights


def compute_data_quality() -> dict:
    """Compute data quality metrics for the network."""
    with get_session() as session:
        total = session.exec(select(func.count(Connection.id))).one()
        scored = session.exec(
            select(func.count(Connection.id))
            .where(Connection.reconnect_score.isnot(None))
        ).one()
        enriched = session.exec(
            select(func.count(Connection.id))
            .where(Connection.enriched_at.isnot(None))
        ).one()
        has_email = session.exec(
            select(func.count(Connection.id))
            .where(Connection.email.isnot(None))
            .where(Connection.email != "")
        ).one()
        has_activity = session.exec(
            select(func.count(Connection.id))
            .where(Connection.activity_log.isnot(None))
        ).one()

        # Funnel stage counts for PWA dashboard view
        reviewed = session.exec(
            select(func.count(OutreachQueueItem.id))
            .where(OutreachQueueItem.status.in_(["approved", "skipped"]))
        ).one()
        reached_out = session.exec(
            select(func.count(OutreachQueueItem.id))
            .where(OutreachQueueItem.status == "sent")
        ).one()
        connected = session.exec(
            select(func.count(OutreachLog.id))
            .where(OutreachLog.outcome == "replied")
        ).one()

    return {
        "total_contacts": total,
        "scored": scored,
        "scored_pct": round(scored / total * 100, 1) if total > 0 else 0,
        "enriched": enriched,
        "enriched_pct": round(enriched / total * 100, 1) if total > 0 else 0,
        "has_email": has_email,
        "email_pct": round(has_email / total * 100, 1) if total > 0 else 0,
        "has_activity": has_activity,
        "need_enrichment": total - enriched,
        "need_email": scored - has_email,
        "reviewed": reviewed,
        "reached_out": reached_out,
        "connected": connected,
    }


def compute_health_breakdown() -> dict:
    """Compute per-component health breakdown with actionable insight text.

    Reuses compute_network_health() to get component values, then wraps each
    component with its weight and an insight string. Also generates a top-level
    insights list highlighting the lowest-scoring areas.

    Returns:
        {
            "score": float,
            "components": {
                "<name>": {"value": float, "weight": float, "insight": str},
                ...
            },
            "insights": [str, ...]  # Top 2 lowest-scoring component insights
        }
    """
    health = compute_network_health()
    components_raw = health.get("components", {})

    # Component weights (must match compute_network_health() weighting)
    weights = {
        "data_completeness": 0.30,
        "enrichment_pct": 0.25,
        "email_coverage_pct": 0.25,
        "activity_score": 0.20,
    }

    components = {}
    for name, value in components_raw.items():
        components[name] = {
            "value": value,
            "weight": weights.get(name, 0.0),
            "insight": _generate_component_insight(name, value),
        }

    # Top-level insights: pick the 2 lowest-scoring components
    sorted_by_value = sorted(components.items(), key=lambda kv: kv[1]["value"])
    insights = [comp_data["insight"] for _, comp_data in sorted_by_value[:2] if comp_data["insight"]]

    return {
        "score": health.get("score", 0),
        "components": components,
        "insights": insights,
    }


def compute_industry_distribution() -> list[dict]:
    """Compute industry distribution across enriched contacts.

    Uses dual-key extraction: company_industry (RapidAPI) or companyIndustry (Apify).
    Only considers contacts with enriched_at IS NOT NULL.
    Returns top 10 industries sorted by count descending with percentages.

    Returns:
        [{"industry": str, "count": int, "pct": float}, ...]
    """
    with get_session() as session:
        enriched = session.exec(
            select(Connection)
            .where(Connection.enriched_at.isnot(None))
        ).all()

    if not enriched:
        return []

    industry_counts: Counter = Counter()
    for conn in enriched:
        enrichment = get_enrichment_data(conn)
        # Dual-key extraction — same pattern as scoring.py and feedback_processor.py
        industry = (
            enrichment.get("company_industry")
            or enrichment.get("companyIndustry")
            or "Unknown"
        )
        industry_counts[industry] += 1

    total = sum(industry_counts.values()) or 1
    return [
        {
            "industry": industry,
            "count": count,
            "pct": round(count / total * 100, 1),
        }
        for industry, count in industry_counts.most_common(10)
    ]


def compute_role_seniority_mix() -> dict:
    """Compute role keyword frequencies and seniority tier distribution.

    Queries Connection.current_role directly (denormalized from enrichment at ingest).
    Extracts role keywords (top 10 by word frequency) and classifies each role
    into one of 4 seniority tiers via _classify_seniority().

    Returns:
        {
            "roles": [{"keyword": str, "count": int}, ...],  # top 10 keywords
            "seniority": [{"tier": str, "count": int}, ...]  # 4 tiers
        }
    """
    with get_session() as session:
        connections = session.exec(
            select(Connection)
            .where(Connection.current_role.isnot(None))
            .where(Connection.current_role != "")
        ).all()

    word_counts: Counter = Counter()
    seniority_counts: Counter = Counter()

    for conn in connections:
        role = conn.current_role or ""
        # Extract individual words for keyword frequency
        words = [w.strip().title() for w in role.split() if len(w.strip()) > 2]
        word_counts.update(words)
        # Classify seniority
        tier = _classify_seniority(role)
        seniority_counts[tier] += 1

    roles = [
        {"keyword": keyword, "count": count}
        for keyword, count in word_counts.most_common(10)
    ]

    # Return all 4 tiers in order (even if count is 0)
    tier_order = ["Executive", "Senior", "Mid-level", "Unknown"]
    seniority = [
        {"tier": tier, "count": seniority_counts.get(tier, 0)}
        for tier in tier_order
        if seniority_counts.get(tier, 0) > 0  # Only include tiers that have contacts
    ]

    return {
        "roles": roles,
        "seniority": seniority,
    }


def compute_score_tier_distribution() -> list[dict]:
    """Compute score tier distribution across scored contacts.

    Buckets: High (>=70), Medium (>=40 and <70), Low (<40).
    Only includes contacts with reconnect_score IS NOT NULL.
    Percentages are computed against total scored contacts.

    Returns:
        [{"tier": str, "count": int, "pct": float}, ...]
    """
    with get_session() as session:
        scored = session.exec(
            select(Connection)
            .where(Connection.reconnect_score.isnot(None))
        ).all()

    # Filter out any None-scored contacts defensively (query should exclude them,
    # but guard here for safety and testability with mock sessions)
    scored_contacts = [c for c in scored if c.reconnect_score is not None]
    high = sum(1 for c in scored_contacts if c.reconnect_score >= 70)
    medium = sum(1 for c in scored_contacts if 40 <= c.reconnect_score < 70)
    low = sum(1 for c in scored_contacts if c.reconnect_score < 40)
    total = len(scored_contacts) or 1

    return [
        {
            "tier": "High (70-100)",
            "count": high,
            "pct": round(high / total * 100, 1),
        },
        {
            "tier": "Medium (40-69)",
            "count": medium,
            "pct": round(medium / total * 100, 1),
        },
        {
            "tier": "Low (0-39)",
            "count": low,
            "pct": round(low / total * 100, 1),
        },
    ]


def compute_dashboard_snapshot() -> dict:
    """Compute full dashboard data and return as dict.

    Called by the pipeline; result is pushed to Supabase as DashboardSnapshot.
    """
    snapshot = {
        "network_health": compute_network_health(),
        "opportunity_alerts": compute_opportunity_alerts(),
        "feedback_insights": compute_feedback_insights(),
        "data_quality": compute_data_quality(),
        # Phase 5 additions:
        "health_breakdown": compute_health_breakdown(),           # DASH-01
        "industry_distribution": compute_industry_distribution(), # DASH-02
        "role_seniority_mix": compute_role_seniority_mix(),      # DASH-03
        "score_tier_distribution": compute_score_tier_distribution(),  # DASH-04
        "computed_at": datetime.utcnow().isoformat(),
    }

    return snapshot


def save_dashboard_snapshot(snapshot_data: dict) -> None:
    """Save a dashboard snapshot to the database."""
    with get_session() as session:
        snapshot = DashboardSnapshot(
            snapshot_type="daily",
            snapshot_data=snapshot_data,
        )
        session.add(snapshot)

    logger.info("Dashboard snapshot saved")
