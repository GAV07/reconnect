"""Push local pipeline results to Supabase cloud DB."""

import logging
from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session, SQLModel, select

from src.database.engine import init_db
from src.database.models import (
    Connection,
    GmailCredentials,
    OutreachLog,
    OutreachQueueItem,
    SyncMetadata,
    UserProfile,
)
from src.sync.engines import get_cloud_engine, get_local_engine

logger = logging.getLogger(__name__)

# Fields to sync for Connection (excludes large blobs and local-only fields)
CONNECTION_SYNC_FIELDS = [
    "id", "name", "email", "linkedin_url",
    "current_role", "current_company", "location",
    "connection_source", "relationship_strength", "tags", "notes",
    "reconnect_score", "score_reasoning", "scored_at",
    "conversation_summary", "conversation_status",
    "message_count", "last_message_date", "last_contacted_at",
    "created_at", "updated_at", "enriched_at",
    "cached_summary", "cached_summary_at",
    "pre_score", "pre_score_tier",
]


def _upsert_record(
    cloud_session: Session,
    model_class: type[SQLModel],
    record_data: dict[str, Any],
    pk_field: str = "id",
):
    """Insert or update a record in the cloud DB."""
    pk_value = record_data[pk_field]
    existing = cloud_session.get(model_class, pk_value)
    if existing:
        for key, value in record_data.items():
            if key != pk_field:
                setattr(existing, key, value)
        cloud_session.add(existing)
    else:
        obj = model_class(**record_data)
        cloud_session.add(obj)


def _get_sync_metadata(session: Session) -> SyncMetadata:
    """Get or create the singleton SyncMetadata row."""
    meta = session.get(SyncMetadata, 1)
    if not meta:
        meta = SyncMetadata(id=1)
        session.add(meta)
        session.flush()
    return meta


def _record_to_dict(record: SQLModel, fields: Optional[list[str]] = None) -> dict[str, Any]:
    """Convert a SQLModel record to a dict, optionally filtering to specific fields."""
    if fields:
        return {f: getattr(record, f) for f in fields if hasattr(record, f)}
    data = {}
    for col in record.__class__.__table__.columns:
        data[col.name] = getattr(record, col.name)
    return data


def push_to_cloud() -> dict[str, Any]:
    """Push finished pipeline results from local SQLite to Supabase cloud.

    Returns:
        Dict with sync stats: connections, queue_items, outreach_logs, etc.
    """
    local_engine = get_local_engine()
    cloud_engine = get_cloud_engine()

    # Ensure cloud tables exist
    init_db(target_engine=cloud_engine)

    stats = {
        "user_profile": 0,
        "connections": 0,
        "queue_items": 0,
        "outreach_logs": 0,
        "gmail_credentials": 0,
    }

    # Get last push timestamp from local DB
    with Session(local_engine, expire_on_commit=False) as local_session:
        meta = _get_sync_metadata(local_session)
        last_push_at = meta.last_push_at
        local_session.commit()

    with Session(cloud_engine, expire_on_commit=False) as cloud_session:
        try:
            # 1. Push UserProfile (tiny singleton, always full upsert)
            with Session(local_engine, expire_on_commit=False) as local_session:
                profile = local_session.get(UserProfile, 1)
                if profile:
                    data = _record_to_dict(profile)
                    _upsert_record(cloud_session, UserProfile, data)
                    stats["user_profile"] = 1

            # 2. Push fully-processed Connections (enriched + scored)
            with Session(local_engine, expire_on_commit=False) as local_session:
                query = select(Connection).where(
                    Connection.enriched_at.is_not(None),
                    Connection.reconnect_score.is_not(None),
                )
                if last_push_at:
                    query = query.where(Connection.updated_at > last_push_at)
                connections = local_session.exec(query).all()

                for conn in connections:
                    data = _record_to_dict(conn, CONNECTION_SYNC_FIELDS)
                    _upsert_record(cloud_session, Connection, data)
                    stats["connections"] += 1

            # 3. Push OutreachQueueItems with drafts
            with Session(local_engine, expire_on_commit=False) as local_session:
                query = select(OutreachQueueItem)
                if last_push_at:
                    query = query.where(OutreachQueueItem.created_at > last_push_at)
                items = local_session.exec(query).all()

                for item in items:
                    data = _record_to_dict(item)
                    _upsert_record(cloud_session, OutreachQueueItem, data)
                    stats["queue_items"] += 1

            # 4. Push OutreachLog history
            with Session(local_engine, expire_on_commit=False) as local_session:
                query = select(OutreachLog)
                if last_push_at:
                    query = query.where(OutreachLog.created_at > last_push_at)
                logs = local_session.exec(query).all()

                for log in logs:
                    data = _record_to_dict(log)
                    _upsert_record(cloud_session, OutreachLog, data)
                    stats["outreach_logs"] += 1

            # 5. Push GmailCredentials (needed for sending from cloud)
            with Session(local_engine, expire_on_commit=False) as local_session:
                creds = local_session.get(GmailCredentials, 1)
                if creds:
                    data = _record_to_dict(creds)
                    _upsert_record(cloud_session, GmailCredentials, data)
                    stats["gmail_credentials"] = 1

            cloud_session.commit()

        except Exception:
            cloud_session.rollback()
            raise

    # Update sync metadata
    with Session(local_engine, expire_on_commit=False) as local_session:
        meta = _get_sync_metadata(local_session)
        meta.last_push_at = datetime.utcnow()
        meta.last_push_connections = stats["connections"]
        meta.last_push_queue_items = stats["queue_items"]
        local_session.add(meta)
        local_session.commit()

    logger.info(
        "Push complete: %d connections, %d queue items, %d outreach logs",
        stats["connections"], stats["queue_items"], stats["outreach_logs"],
    )
    return stats
