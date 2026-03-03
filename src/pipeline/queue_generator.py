"""Outreach queue generation for Reconnect.

Generates daily queue of contacts to reach out to, with intelligent
exclusion rules and channel selection.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import select

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection, OutreachQueueItem, UserProfile


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
    return OutreachQueueItem(
        connection_id=connection.id,
        channel=channel,
        draft_message=None,
        draft_subject=f"Reconnecting - {user_profile.name or 'Hi'}" if channel == "email" else None,
        priority_score=connection.reconnect_score or connection.pre_score or 50,
        status="pending_review",
    )


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
        Dict with stats: {"added": N, "excluded": N, "exclusion_reasons": {...}}
    """
    if limit is None:
        limit = settings.daily_queue_size

    stats = {
        "added": 0,
        "excluded": 0,
        "exclusion_reasons": {},
    }

    with get_session() as session:
        user_profile = session.get(UserProfile, 1)
        if not user_profile:
            user_profile = UserProfile(id=1, name="")

        # Get top-scored connections - only those with a full reconnect_score
        query = (
            select(Connection)
            .where(Connection.reconnect_score.isnot(None))
            .where(Connection.reconnect_score >= settings.min_queue_score)
            .order_by(Connection.reconnect_score.desc())
            .limit(limit * 3)  # Fetch extra in case of exclusions
        )

        candidates = session.exec(query).all()

        added = 0
        for conn in candidates:
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

            # Determine channel and create queue item
            channel = determine_channel(conn)
            queue_item = generate_queue_item(conn, user_profile, channel)

            session.add(queue_item)
            added += 1

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
