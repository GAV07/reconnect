"""Pull user actions from Supabase cloud DB back to local SQLite."""

import logging
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from src.database.models import (
    Connection,
    OutreachLog,
    OutreachQueueItem,
    SyncMetadata,
)
from src.sync.engines import get_cloud_engine, get_local_engine

logger = logging.getLogger(__name__)


def _get_sync_metadata(session: Session) -> SyncMetadata:
    """Get or create the singleton SyncMetadata row."""
    meta = session.get(SyncMetadata, 1)
    if not meta:
        meta = SyncMetadata(id=1)
        session.add(meta)
        session.flush()
    return meta


def pull_from_cloud() -> dict[str, Any]:
    """Pull user review actions from Supabase cloud back to local SQLite.

    Syncs:
    - OutreachQueueItem status changes (approved/skipped/sent) and message edits
    - Connection.last_contacted_at updates
    - OutreachLog entries created from cloud sends

    Conflict resolution: cloud wins for review actions, most-recent-wins for timestamps.

    Returns:
        Dict with pull stats.
    """
    local_engine = get_local_engine()
    cloud_engine = get_cloud_engine()

    stats = {
        "queue_items_updated": 0,
        "contacts_updated": 0,
        "outreach_logs_pulled": 0,
    }

    # Get last pull timestamp
    with Session(local_engine, expire_on_commit=False) as local_session:
        meta = _get_sync_metadata(local_session)
        last_pull_at = meta.last_pull_at
        local_session.commit()

    with Session(cloud_engine, expire_on_commit=False) as cloud_session:
        # 1. Pull OutreachQueueItem status changes (cloud wins)
        query = select(OutreachQueueItem).where(
            OutreachQueueItem.status.in_(["approved", "skipped", "sent"])
        )
        if last_pull_at:
            query = query.where(OutreachQueueItem.reviewed_at > last_pull_at)
        cloud_items = cloud_session.exec(query).all()

        # Detach data before opening local session
        items_data = []
        for item in cloud_items:
            items_data.append({
                "id": item.id,
                "status": item.status,
                "skip_reason": item.skip_reason,
                "reviewed_at": item.reviewed_at,
                "sent_at": item.sent_at,
                "draft_message": item.draft_message,
                "draft_subject": item.draft_subject,
            })

        # 2. Pull OutreachLog entries created on cloud
        log_query = select(OutreachLog)
        if last_pull_at:
            log_query = log_query.where(OutreachLog.created_at > last_pull_at)
        cloud_logs = cloud_session.exec(log_query).all()

        logs_data = []
        for log in cloud_logs:
            logs_data.append({
                "id": log.id,
                "connection_id": log.connection_id,
                "channel": log.channel,
                "generated_prose": log.generated_prose,
                "sent_at": log.sent_at,
                "outcome": log.outcome,
                "outcome_at": log.outcome_at,
                "created_at": log.created_at,
            })

        # 3. Pull Connection.last_contacted_at updates
        contact_query = select(Connection).where(
            Connection.last_contacted_at.is_not(None)
        )
        if last_pull_at:
            contact_query = contact_query.where(Connection.updated_at > last_pull_at)
        cloud_contacts = cloud_session.exec(contact_query).all()

        contacts_data = []
        for conn in cloud_contacts:
            contacts_data.append({
                "id": conn.id,
                "last_contacted_at": conn.last_contacted_at,
            })

    # Apply changes to local DB
    with Session(local_engine, expire_on_commit=False) as local_session:
        try:
            # Apply queue item updates (cloud wins)
            for item_data in items_data:
                local_item = local_session.get(OutreachQueueItem, item_data["id"])
                if local_item:
                    local_item.status = item_data["status"]
                    local_item.skip_reason = item_data["skip_reason"]
                    local_item.reviewed_at = item_data["reviewed_at"]
                    local_item.sent_at = item_data["sent_at"]
                    local_item.draft_message = item_data["draft_message"]
                    local_item.draft_subject = item_data["draft_subject"]
                    local_session.add(local_item)
                    stats["queue_items_updated"] += 1

            # Apply outreach log entries (insert if not exists)
            for log_data in logs_data:
                existing = local_session.get(OutreachLog, log_data["id"])
                if not existing:
                    log_obj = OutreachLog(**log_data)
                    local_session.add(log_obj)
                    stats["outreach_logs_pulled"] += 1

            # Apply last_contacted_at updates (most-recent-wins)
            for contact_data in contacts_data:
                local_conn = local_session.get(Connection, contact_data["id"])
                if local_conn:
                    cloud_ts = contact_data["last_contacted_at"]
                    local_ts = local_conn.last_contacted_at
                    if local_ts is None or (cloud_ts and cloud_ts > local_ts):
                        local_conn.last_contacted_at = cloud_ts
                        local_session.add(local_conn)
                        stats["contacts_updated"] += 1

            # Update sync metadata
            meta = _get_sync_metadata(local_session)
            meta.last_pull_at = datetime.utcnow()
            meta.last_pull_actions = (
                stats["queue_items_updated"]
                + stats["outreach_logs_pulled"]
                + stats["contacts_updated"]
            )
            local_session.add(meta)

            local_session.commit()

        except Exception:
            local_session.rollback()
            raise

    logger.info(
        "Pull complete: %d queue items, %d logs, %d contacts updated",
        stats["queue_items_updated"], stats["outreach_logs_pulled"], stats["contacts_updated"],
    )
    return stats
