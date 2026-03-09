"""Dashboard computation service — shared by pipeline and Streamlit.

Computes network health, opportunity alerts, feedback insights, and
data quality metrics. Pipeline pushes results to Supabase as a
DashboardSnapshot for the PWA to read.
"""

import json
import logging
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


def compute_dashboard_snapshot() -> dict:
    """Compute full dashboard data and return as dict.

    Called by the pipeline; result is pushed to Supabase as DashboardSnapshot.
    """
    snapshot = {
        "network_health": compute_network_health(),
        "opportunity_alerts": compute_opportunity_alerts(),
        "feedback_insights": compute_feedback_insights(),
        "data_quality": compute_data_quality(),
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
