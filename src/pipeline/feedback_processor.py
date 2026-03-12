"""Feedback processor — analyzes user behavior to tune scoring weights.

Runs as a daily pipeline step. Analyzes skip/approval patterns, signal triage
patterns, and digest ratings to derive scoring weight adjustments.
"""

import logging
from collections import Counter
from datetime import datetime, timedelta

from sqlmodel import select

from src.database.engine import get_session
from src.database.models import (
    Connection,
    ContactSignal,
    OutreachQueueItem,
    UserFeedback,
    UserPreference,
)

logger = logging.getLogger(__name__)

# Safety guard constants (locked decisions — see Phase 9 research)
MIN_ACTIONS_FOR_ADJUSTMENT = 25  # Minimum total actions before any weight change
MAX_MULTIPLIER = 1.4             # All multipliers clamped to [0.6, 1.4]
MIN_MULTIPLIER = 0.6


def process_feedback() -> dict:
    """Analyze feedback signals and update scoring weights.

    Returns:
        Dict with processing stats.
    """
    stats = {
        "skip_patterns_analyzed": 0,
        "approval_patterns_analyzed": 0,
        "signal_patterns_analyzed": 0,
        "weight_adjustments": 0,
        "insights": [],
    }

    skip_insights = _analyze_skip_patterns()
    stats["skip_patterns_analyzed"] = skip_insights["total_analyzed"]
    stats["insights"].extend(skip_insights.get("insights", []))

    approval_insights = _analyze_approval_patterns()
    stats["approval_patterns_analyzed"] = approval_insights["total_analyzed"]
    stats["insights"].extend(approval_insights.get("insights", []))

    signal_insights = _analyze_signal_patterns()
    stats["signal_patterns_analyzed"] = signal_insights["total_analyzed"]

    # Derive and apply weight adjustments (with signal insights)
    adjustments = _derive_weight_adjustments(skip_insights, approval_insights, signal_insights)
    for dim_name, multiplier in adjustments.items():
        _upsert_scoring_weight(dim_name, multiplier)
        _log_weight_history(dim_name, multiplier)
        stats["weight_adjustments"] += 1

    logger.info(
        "Feedback processing: %d skips, %d approvals, %d signals analyzed, %d weight adjustments",
        stats["skip_patterns_analyzed"],
        stats["approval_patterns_analyzed"],
        stats["signal_patterns_analyzed"],
        stats["weight_adjustments"],
    )
    return stats


def _analyze_skip_patterns() -> dict:
    """Analyze which types of contacts get skipped."""
    cutoff = datetime.utcnow() - timedelta(days=30)

    with get_session() as session:
        skipped = session.exec(
            select(OutreachQueueItem)
            .where(OutreachQueueItem.status == "skipped")
            .where(OutreachQueueItem.reviewed_at >= cutoff)
        ).all()

        if not skipped:
            return {"total_analyzed": 0, "insights": []}

        industry_skips: Counter = Counter()
        company_skips: Counter = Counter()
        role_skips: Counter = Counter()

        for item in skipped:
            conn = session.get(Connection, item.connection_id)
            if not conn:
                continue

            enrichment = conn.raw_enrichment or {}
            if "data" in enrichment and isinstance(enrichment["data"], dict):
                enrichment = enrichment["data"]

            industry = enrichment.get("company_industry") or enrichment.get("companyIndustry")
            if industry:
                industry_skips[industry.lower()] += 1

            if conn.current_company:
                company_skips[conn.current_company.lower()] += 1

            if conn.current_role:
                # Extract role keywords
                role_lower = conn.current_role.lower()
                for kw in ["marketing", "sales", "engineering", "product", "design", "finance", "hr", "legal"]:
                    if kw in role_lower:
                        role_skips[kw] += 1

    total = len(skipped)
    insights = []

    # Find dominant skip patterns (>40% of skips)
    for industry, count in industry_skips.most_common(3):
        pct = count / total * 100
        if pct >= 40:
            insights.append(f"Skipped {pct:.0f}% of {industry} contacts")

    for role_kw, count in role_skips.most_common(3):
        pct = count / total * 100
        if pct >= 40:
            insights.append(f"Skipped {pct:.0f}% of {role_kw} contacts")

    return {"total_analyzed": total, "insights": insights, "industry_skips": dict(industry_skips), "role_skips": dict(role_skips)}


def _analyze_approval_patterns() -> dict:
    """Analyze which types of contacts get approved."""
    cutoff = datetime.utcnow() - timedelta(days=30)

    with get_session() as session:
        approved = session.exec(
            select(OutreachQueueItem)
            .where(OutreachQueueItem.status.in_(["approved", "sent"]))
            .where(OutreachQueueItem.reviewed_at >= cutoff)
        ).all()

        if not approved:
            return {"total_analyzed": 0, "insights": []}

        industry_approvals: Counter = Counter()
        seniority_approvals: Counter = Counter()

        for item in approved:
            conn = session.get(Connection, item.connection_id)
            if not conn:
                continue

            enrichment = conn.raw_enrichment or {}
            if "data" in enrichment and isinstance(enrichment["data"], dict):
                enrichment = enrichment["data"]

            industry = enrichment.get("company_industry") or enrichment.get("companyIndustry")
            if industry:
                industry_approvals[industry.lower()] += 1

            if conn.current_role:
                role_lower = conn.current_role.lower()
                if any(t in role_lower for t in ["vp", "director", "head", "chief", "ceo", "cto", "coo"]):
                    seniority_approvals["senior"] += 1
                elif any(t in role_lower for t in ["manager", "lead"]):
                    seniority_approvals["mid"] += 1
                else:
                    seniority_approvals["junior"] += 1

    total = len(approved)
    insights = []

    for industry, count in industry_approvals.most_common(3):
        pct = count / total * 100
        if pct >= 30:
            insights.append(f"Approved {pct:.0f}% from {industry}")

    return {"total_analyzed": total, "insights": insights, "industry_approvals": dict(industry_approvals)}


def _analyze_signal_patterns(days: int = 14) -> dict:
    """Analyze ContactSignal assignments for weight adjustment hints.

    Only analyzes user-driven signals (assigned_by='user'). System and
    pipeline signals reflect automated behavior, not user preference.

    Returns signal frequency data from the last N days.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    with get_session() as session:
        signals = session.exec(
            select(ContactSignal)
            .where(ContactSignal.assigned_at >= cutoff)
            .where(ContactSignal.assigned_by == "user")
        ).all()

    signal_counts = Counter(s.signal for s in signals)
    total = len(signals)
    return {
        "total_analyzed": total,
        "signal_counts": dict(signal_counts),
    }


def _log_weight_history(dimension: str, multiplier: float) -> None:
    """Log a weight adjustment for auditability. Insert-only (never upserted)."""
    with get_session() as session:
        history_row = UserPreference(
            pref_type="weight_history",
            pref_key=dimension,
            pref_value=str(round(multiplier, 4)),
        )
        session.add(history_row)


def _derive_weight_adjustments(
    skip_insights: dict,
    approval_insights: dict,
    signal_insights: dict | None = None,
) -> dict[str, float]:
    """Derive scoring dimension weight adjustments from patterns.

    Safety guards (locked decisions):
    - Minimum 25 total actions before any adjustment
    - All multipliers clamped to [0.6, 1.4]

    Signal pattern -> weight mapping:
    - High WARM_LEAD rate (>40%) -> boost goal_alignment (user finds goal-aligned contacts valuable)
    - High FUTURE_PIVOT rate (>40%) -> reduce mutual_value (contacts not immediately valuable)
    - High NURTURE rate (>40%) -> boost network_reach (user values long-term connectors)
    - High ARCHIVE rate -> NO weight change (ARCHIVE = contact irrelevant, not a scoring quality signal
      per research pitfall 3 — ARCHIVE means contact irrelevant, not that hooks were bad)
    """
    adjustments: dict[str, float] = {}

    approval_total = approval_insights.get("total_analyzed", 0)
    skip_total = skip_insights.get("total_analyzed", 0)
    signal_total = (signal_insights or {}).get("total_analyzed", 0)
    total_actions = approval_total + skip_total + signal_total

    if total_actions < MIN_ACTIONS_FOR_ADJUSTMENT:
        return adjustments  # Not enough data — locked decision

    # Approval/skip-based adjustments (existing logic, updated)
    if approval_total + skip_total > 0:
        approval_rate = approval_total / (approval_total + skip_total)
        if approval_rate < 0.3 and (approval_total + skip_total) >= 15:
            adjustments["conversation_hooks"] = 0.9
        if approval_rate > 0.7 and (approval_total + skip_total) >= 15:
            adjustments["goal_alignment"] = adjustments.get("goal_alignment", 1.0) * 1.1

    # Signal pattern-based adjustments
    if signal_insights and signal_total > 0:
        signal_counts = signal_insights.get("signal_counts", {})

        warm_lead_pct = signal_counts.get("WARM_LEAD", 0) / signal_total
        future_pivot_pct = signal_counts.get("FUTURE_PIVOT", 0) / signal_total
        nurture_pct = signal_counts.get("NURTURE", 0) / signal_total
        # Note: ARCHIVE rate intentionally NOT used for weight adjustment
        # (per research pitfall 3 — ARCHIVE means contact irrelevant, not a
        # signal about scoring dimension quality)

        if warm_lead_pct > 0.4:
            adjustments["goal_alignment"] = adjustments.get("goal_alignment", 1.0) * 1.15
        if future_pivot_pct > 0.4:
            adjustments["mutual_value"] = adjustments.get("mutual_value", 1.0) * 0.85
        if nurture_pct > 0.4:
            adjustments["network_reach"] = adjustments.get("network_reach", 1.0) * 1.1

    # SAFETY GUARD: clamp all multipliers to [MIN_MULTIPLIER, MAX_MULTIPLIER]
    for dim in adjustments:
        adjustments[dim] = max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, adjustments[dim]))

    return adjustments


def _upsert_scoring_weight(dimension: str, multiplier: float) -> None:
    """Insert or update a scoring weight preference."""
    with get_session() as session:
        existing = session.exec(
            select(UserPreference)
            .where(UserPreference.pref_type == "scoring_weight")
            .where(UserPreference.pref_key == dimension)
            .where(UserPreference.is_active == True)
        ).first()

        if existing:
            existing.pref_value = str(multiplier)
            session.add(existing)
        else:
            pref = UserPreference(
                pref_type="scoring_weight",
                pref_key=dimension,
                pref_value=str(multiplier),
            )
            session.add(pref)
