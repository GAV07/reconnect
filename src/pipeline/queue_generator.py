"""Outreach queue generation for Reconnect.

Generates daily queue of contacts to reach out to, with intelligent
exclusion rules and channel selection.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import or_
from sqlmodel import select

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection, OutreachQueueItem, UserPreference, UserProfile


@dataclass
class ExclusionResult:
    """Result of checking exclusion rules."""

    excluded: bool
    reason: Optional[str] = None


def is_contact_excluded(connection: Connection) -> ExclusionResult:
    """
    Check if a contact should be excluded from outreach queue.

    Exclusion rules:
    1. Active conversation (last message within N days)
    2. Recently contacted (last_contacted_at within N days)
    3. Already in queue (pending_review or approved status)
    4. No email AND no LinkedIn URL (no way to reach them)

    Args:
        connection: Connection to check

    Returns:
        ExclusionResult with excluded flag and reason
    """
    now = datetime.utcnow()

    # Rule 1: Active conversation
    if connection.last_message_date:
        days_since_message = (now - connection.last_message_date).days
        if days_since_message <= settings.active_conversation_days:
            return ExclusionResult(
                excluded=True,
                reason=f"Active conversation ({days_since_message} days ago)"
            )

    # Rule 2: Recently contacted
    if connection.last_contacted_at:
        days_since_contact = (now - connection.last_contacted_at).days
        if days_since_contact <= settings.recently_contacted_days:
            return ExclusionResult(
                excluded=True,
                reason=f"Recently contacted ({days_since_contact} days ago)"
            )

    # Rule 3: Already in queue or recently skipped
    with get_session() as session:
        # Block if pending or approved
        active_item = session.exec(
            select(OutreachQueueItem)
            .where(OutreachQueueItem.connection_id == connection.id)
            .where(OutreachQueueItem.status.in_(["pending_review", "approved"]))
        ).first()

        if active_item:
            return ExclusionResult(
                excluded=True,
                reason=f"Already in queue (status: {active_item.status})"
            )

        # Block if skipped within cooldown period
        cooldown_cutoff = now - timedelta(days=settings.skip_cooldown_days)
        skipped_item = session.exec(
            select(OutreachQueueItem)
            .where(OutreachQueueItem.connection_id == connection.id)
            .where(OutreachQueueItem.status == "skipped")
            .where(OutreachQueueItem.reviewed_at >= cooldown_cutoff)
        ).first()

        if skipped_item:
            days_ago = (now - skipped_item.reviewed_at).days
            return ExclusionResult(
                excluded=True,
                reason=f"Skipped {days_ago} days ago (cooldown: {settings.skip_cooldown_days}d)"
            )

    # Rule 4: No contact method
    if not connection.email and not connection.linkedin_url:
        return ExclusionResult(
            excluded=True,
            reason="No email or LinkedIn URL"
        )

    # Rule 5: User marked as "never suggest"
    if hasattr(connection, "user_priority") and connection.user_priority == "never":
        return ExclusionResult(
            excluded=True,
            reason="User marked as never suggest"
        )

    return ExclusionResult(excluded=False)


def determine_channel(connection: Connection) -> str:
    """
    Determine best outreach channel for a contact.

    Priority:
    1. Email if available (higher response rate, more personal)
    2. LinkedIn if has URL

    Args:
        connection: Connection to determine channel for

    Returns:
        Channel string: "email" or "linkedin"
    """
    if connection.email:
        return "email"
    elif connection.linkedin_url:
        return "linkedin"
    else:
        return "linkedin"  # Default, though this shouldn't happen


def generate_queue_item(
    connection: Connection,
    user_profile: UserProfile,
    channel: str,
) -> OutreachQueueItem:
    """
    Create a queue item without a draft message.

    Draft messages are generated on-demand in the review UI to save LLM credits.

    Args:
        connection: Connection to create item for
        user_profile: User profile for message generation
        channel: Outreach channel

    Returns:
        OutreachQueueItem ready for review
    """
    # Compute why_today hook
    why_today = _compute_why_today(connection)

    return OutreachQueueItem(
        connection_id=connection.id,
        channel=channel,
        draft_message=None,
        draft_subject=f"Reconnecting - {user_profile.name or 'Hi'}" if channel == "email" else None,
        priority_score=connection.reconnect_score or connection.pre_score or 50,
        status="pending_review",
        why_today=why_today,
    )


def reset_queue() -> dict:
    """Mark all pending_review and approved items as skipped.

    Returns:
        Dict with count of items reset: {"reset": N}
    """
    with get_session() as session:
        items = session.exec(
            select(OutreachQueueItem)
            .where(OutreachQueueItem.status.in_(["pending_review", "approved"]))
        ).all()
        count = 0
        for item in items:
            item.status = "skipped"
            item.skip_reason = "Queue reset via CLI"
            item.reviewed_at = datetime.utcnow()
            session.add(item)
            count += 1
    return {"reset": count}


def expire_stale_queue_items(max_age_days: int = 7) -> int:
    """
    Mark pending_review/approved queue items older than max_age_days as skipped.

    Returns:
        Number of items expired
    """
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)

    with get_session() as session:
        stale_items = session.exec(
            select(OutreachQueueItem)
            .where(OutreachQueueItem.status.in_(["pending_review", "approved"]))
            .where(OutreachQueueItem.created_at < cutoff)
        ).all()

        count = 0
        for item in stale_items:
            item.status = "skipped"
            item.skip_reason = f"Auto-expired after {max_age_days} days"
            item.reviewed_at = datetime.utcnow()
            session.add(item)
            count += 1

    return count


def _compute_why_today(connection: Connection) -> Optional[str]:
    """Compute a time-sensitive reason to reach out today."""
    import json

    reasons = []

    # Check for recent job change from enrichment
    enrichment = connection.raw_enrichment or {}
    if "data" in enrichment and isinstance(enrichment["data"], dict):
        enrichment = enrichment["data"]

    join_year = enrichment.get("current_company_join_year")
    join_month = enrichment.get("current_company_join_month")
    if join_year and join_month:
        try:
            job_start = datetime(int(join_year), int(join_month), 1)
            months = (datetime.utcnow() - job_start).days / 30
            if months < 6:
                reasons.append(f"Changed jobs {months:.0f} months ago")
        except (ValueError, TypeError):
            pass

    # Check for recent activity
    if connection.activity_log and len(connection.activity_log) > 0:
        latest = connection.activity_log[0]
        content = latest.get("content", "")[:80]
        if content:
            reasons.append(f"Recent post: {content}")

    # Extract hooks from score_reasoning
    if connection.score_reasoning:
        try:
            reasoning = json.loads(connection.score_reasoning)
            hooks = reasoning.get("conversation_hooks", [])
            if isinstance(hooks, list):
                for hook in hooks[:1]:
                    if hook and str(hook) not in str(reasons):
                        reasons.append(str(hook))
        except (json.JSONDecodeError, TypeError):
            pass

    # Stale high-value connection
    if connection.reconnect_score and connection.reconnect_score >= 70:
        if connection.last_contacted_at:
            days = (datetime.utcnow() - connection.last_contacted_at).days
            if days > 90:
                reasons.append(f"High-value connection, last contact {days} days ago")
        elif connection.last_message_date:
            days = (datetime.utcnow() - connection.last_message_date).days
            if days > 90:
                reasons.append(f"Haven't connected in {days} days")

    return reasons[0] if reasons else None


def _get_cadence_expired_candidates(session, limit: int) -> list[Connection]:
    """Get contacts whose cadence has expired and are eligible for re-queuing.

    Uses the stored cadence_due_at field (computed at signal assignment time
    as assigned_at + cadence_days). Does NOT re-derive cadence from signals.

    ARCHIVE contacts (user_priority='never') are excluded here AND by
    is_contact_excluded() downstream — belt and suspenders.

    Args:
        session: Active database session
        limit: Max candidates to return (should be limit // 2 for volume cap)

    Returns:
        List of Connection objects ordered by reconnect_score desc
    """
    now = datetime.utcnow()
    return session.exec(
        select(Connection)
        .where(Connection.cadence_due_at.isnot(None))
        .where(Connection.cadence_due_at <= now)
        .where(
            or_(
                Connection.user_priority.is_(None),
                Connection.user_priority != "never",
            )
        )
        .where(Connection.reconnect_score.isnot(None))
        .order_by(Connection.reconnect_score.desc())
        .limit(limit)
    ).all()


def _get_scoring_weight_multipliers() -> dict[str, float]:
    """Load scoring weight multipliers from user preferences."""
    multipliers = {}
    with get_session() as session:
        prefs = session.exec(
            select(UserPreference)
            .where(UserPreference.pref_type == "scoring_weight")
            .where(UserPreference.is_active == True)
        ).all()
        for pref in prefs:
            try:
                multipliers[pref.pref_key] = float(pref.pref_value)
            except (ValueError, TypeError):
                pass
    return multipliers


def _apply_weight_multipliers(connection: Connection, multipliers: dict[str, float]) -> float:
    """Apply user preference weight multipliers to a connection's score."""
    import json

    base_score = connection.reconnect_score or connection.pre_score or 0
    if not multipliers or not connection.score_reasoning:
        return base_score

    try:
        reasoning = json.loads(connection.score_reasoning)
        dims = reasoning.get("dimension_scores", {})
        if not dims:
            return base_score

        adjusted = 0
        for dim_name, dim_score in dims.items():
            multiplier = multipliers.get(dim_name, 1.0)
            adjusted += dim_score * multiplier

        return adjusted
    except (json.JSONDecodeError, TypeError):
        return base_score


def generate_daily_queue(limit: Optional[int] = None) -> dict:
    """
    Generate daily outreach queue from top-scored contacts.

    Selects contacts based on:
    1. Reconnect score (if enriched) or pre-score
    2. Not excluded by any rules
    3. Limited to daily quota

    Args:
        limit: Max items to add (defaults to settings.daily_queue_size)

    Returns:
        Dict with stats: {"added": N, "excluded": N, "expired": N, "exclusion_reasons": {...}}
    """
    if limit is None:
        limit = settings.daily_queue_size

    # Expire stale items first so their contacts can re-enter the queue
    expired = expire_stale_queue_items()

    stats = {
        "added": 0,
        "excluded": 0,
        "expired": expired,
        "cadence_added": 0,
        "exclusion_reasons": {},
    }

    # Load scoring weight multipliers from user preferences
    multipliers = _get_scoring_weight_multipliers()

    with get_session() as session:
        user_profile = session.get(UserProfile, 1)
        if not user_profile:
            user_profile = UserProfile(id=1, name="")

        # First: include "always" priority contacts (if not on cooldown)
        always_contacts = session.exec(
            select(Connection)
            .where(Connection.user_priority == "always")
            .where(Connection.reconnect_score.isnot(None))
        ).all()

        # Cadence re-queuing: contacts whose cadence timer has expired
        # Volume cap: at most half the queue slots go to cadence re-queues (CAD-03)
        cadence_limit = limit // 2
        cadence_candidates = _get_cadence_expired_candidates(session, cadence_limit)

        # Get top-scored connections - only those with a full reconnect_score
        query = (
            select(Connection)
            .where(Connection.reconnect_score.isnot(None))
            .where(Connection.reconnect_score >= settings.min_queue_score)
            .order_by(Connection.reconnect_score.desc())
            .limit(limit * 3)  # Fetch extra in case of exclusions
        )

        candidates = session.exec(query).all()

        # Merge: always contacts first, then cadence re-queues, then fresh scored
        always_ids = {c.id for c in always_contacts}
        cadence_ids = {c.id for c in cadence_candidates}
        merged = list(always_contacts)
        for c in cadence_candidates:
            if c.id not in always_ids:
                merged.append(c)
        for c in candidates:
            if c.id not in always_ids and c.id not in cadence_ids:
                merged.append(c)

        # Apply weight multipliers and re-sort (always contacts stay at top)
        if multipliers:
            for conn in merged:
                if conn.id not in always_ids:
                    conn._adjusted_score = _apply_weight_multipliers(conn, multipliers)
                else:
                    conn._adjusted_score = 999  # Always contacts sort first
            merged.sort(key=lambda c: getattr(c, "_adjusted_score", 0), reverse=True)

        added = 0
        company_counts: dict[str, int] = {}  # For diversification

        for conn in merged:
            if added >= limit:
                break

            # Check exclusions
            exclusion = is_contact_excluded(conn)
            if exclusion.excluded:
                stats["excluded"] += 1
                reason = exclusion.reason or "Unknown"
                stats["exclusion_reasons"][reason] = (
                    stats["exclusion_reasons"].get(reason, 0) + 1
                )
                continue

            # Diversification: max 2 contacts from same company
            if conn.current_company:
                company_key = conn.current_company.lower().strip()
                if company_counts.get(company_key, 0) >= 2:
                    stats["excluded"] += 1
                    stats["exclusion_reasons"]["Company diversity limit"] = (
                        stats["exclusion_reasons"].get("Company diversity limit", 0) + 1
                    )
                    continue
                company_counts[company_key] = company_counts.get(company_key, 0) + 1

            # Determine channel and create queue item
            channel = determine_channel(conn)
            queue_item = generate_queue_item(conn, user_profile, channel)

            session.add(queue_item)
            added += 1
            if conn.id in cadence_ids:
                stats["cadence_added"] = stats.get("cadence_added", 0) + 1

        stats["added"] = added

    return stats


def get_pending_queue() -> list[tuple[OutreachQueueItem, Connection]]:
    """
    Get all pending review items with their connections.

    Returns:
        List of (queue_item, connection) tuples sorted by priority
    """
    with get_session() as session:
        items = session.exec(
            select(OutreachQueueItem)
            .where(OutreachQueueItem.status == "pending_review")
            .order_by(OutreachQueueItem.priority_score.desc())
        ).all()

        result = []
        for item in items:
            conn = session.get(Connection, item.connection_id)
            if conn:
                # Detach from session - load all attributes needed by review page
                _ = item.id, item.draft_message, item.channel, item.draft_subject
                _ = conn.id, conn.name, conn.current_role, conn.current_company
                _ = conn.email, conn.linkedin_url, conn.reconnect_score, conn.pre_score
                _ = conn.location, conn.score_reasoning
                _ = conn.raw_enrichment, conn.activity_log
                result.append((item, conn))

        return result


def approve_queue_item(item_id: int, edited_message: Optional[str] = None) -> bool:
    """
    Approve a queue item for sending.

    Args:
        item_id: Queue item ID
        edited_message: Optional edited message to use

    Returns:
        True if approved successfully
    """
    with get_session() as session:
        item = session.get(OutreachQueueItem, item_id)
        if not item:
            return False

        if edited_message:
            item.draft_message = edited_message

        item.status = "approved"
        item.reviewed_at = datetime.utcnow()
        session.add(item)

    return True


def skip_queue_item(item_id: int, reason: Optional[str] = None) -> bool:
    """
    Skip a queue item.

    Args:
        item_id: Queue item ID
        reason: Optional reason for skipping

    Returns:
        True if skipped successfully
    """
    with get_session() as session:
        item = session.get(OutreachQueueItem, item_id)
        if not item:
            return False

        item.status = "skipped"
        item.skip_reason = reason
        item.reviewed_at = datetime.utcnow()
        session.add(item)

    return True


def mark_item_sent(item_id: int) -> bool:
    """
    Mark a queue item as sent.

    Args:
        item_id: Queue item ID

    Returns:
        True if marked successfully
    """
    with get_session() as session:
        item = session.get(OutreachQueueItem, item_id)
        if not item:
            return False

        item.status = "sent"
        item.sent_at = datetime.utcnow()
        session.add(item)

        # Also update the connection's last_contacted_at
        conn = session.get(Connection, item.connection_id)
        if conn:
            conn.last_contacted_at = datetime.utcnow()
            session.add(conn)

    return True


def get_queue_stats() -> dict:
    """
    Get current queue statistics.

    Returns:
        Dict with counts by status
    """
    with get_session() as session:
        from sqlmodel import func

        stats = {}
        for status in ["pending_review", "approved", "skipped", "sent", "failed"]:
            count = session.exec(
                select(func.count(OutreachQueueItem.id))
                .where(OutreachQueueItem.status == status)
            ).one()
            stats[status] = count

        return stats
