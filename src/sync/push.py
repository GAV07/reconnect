"""Push local pipeline results to Supabase cloud DB."""

import logging
from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session, SQLModel, select

from src.database.engine import init_db
from src.database.models import (
    ActionToken,
    Connection,
    ContactNote,
    ContactSignal,
    DashboardSnapshot,
    EngagementSignal,
    OutreachLog,
    OutreachQueueItem,
    SyncMetadata,
    UserContent,
    UserFeedback,
    UserPreference,
    UserProfile,
)
from src.sync.engines import get_cloud_engine, get_local_engine

logger = logging.getLogger(__name__)

# Fields to sync for Connection
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
    # Enrichment data (needed for detail views)
    "raw_enrichment", "activity_log",
    # Engagement fields
    "engagement_score", "last_engagement_date", "engagement_direction",
    "endorsement_count", "has_recommendation",
    # PWA overhaul fields
    "user_priority", "data_completeness_score", "missing_data_fields",
    # Signal foundation fields (Phase 7)
    "latest_signal", "cadence_due_at",
    # Enrichment extracted columns (Phase 12)
    "enriched_industry", "enriched_headline", "enriched_city",
    "enriched_country", "enriched_school", "enriched_seniority",
    "education_text",
    # Acquisition pipeline fields (v1.4)
    "acquisition_role", "pipeline_stage",
    "pipeline_notes", "pipeline_updated_at",
    # Semantic search (v2.0)
    "profile_text", "profile_embedding",
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
        "engagement_signals": 0,
        "user_content": 0,
        "action_tokens": 0,
        "user_feedback": 0,
        "user_preferences": 0,
        "dashboard_snapshots": 0,
        "contact_signals": 0,
        "contact_notes": 0,
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

            # 2. Push connections that have been scored or have queue items
            with Session(local_engine, expire_on_commit=False) as local_session:
                # Get IDs of connections that are in the outreach queue
                queued_ids = set(
                    local_session.exec(select(OutreachQueueItem.connection_id)).all()
                )

                query = select(Connection).where(
                    # Enriched + scored OR pre-scored OR has a queue item
                    (Connection.reconnect_score.is_not(None))
                    | (Connection.pre_score.is_not(None))
                )
                if last_push_at:
                    query = query.where(Connection.updated_at > last_push_at)
                connections = local_session.exec(query).all()

                # Also include any queued connections not yet captured
                if queued_ids:
                    queued_conns = local_session.exec(
                        select(Connection).where(Connection.id.in_(queued_ids))
                    ).all()
                    seen_ids = {c.id for c in connections}
                    for c in queued_conns:
                        if c.id not in seen_ids:
                            connections.append(c)

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

            # 5. GmailCredentials removed -- OAuth tokens stay local only (security)

            # 6. Push EngagementSignals
            with Session(local_engine, expire_on_commit=False) as local_session:
                query = select(EngagementSignal)
                if last_push_at:
                    query = query.where(EngagementSignal.created_at > last_push_at)
                signals = local_session.exec(query).all()

                for signal in signals:
                    data = _record_to_dict(signal)
                    _upsert_record(cloud_session, EngagementSignal, data)
                    stats["engagement_signals"] += 1

            # 7. Push UserContent
            with Session(local_engine, expire_on_commit=False) as local_session:
                query = select(UserContent)
                if last_push_at:
                    query = query.where(UserContent.created_at > last_push_at)
                contents = local_session.exec(query).all()

                for content in contents:
                    data = _record_to_dict(content)
                    _upsert_record(cloud_session, UserContent, data)
                    stats["user_content"] += 1

            # 8. Push ActionTokens (new, unexpired)
            with Session(local_engine, expire_on_commit=False) as local_session:
                query = select(ActionToken)
                if last_push_at:
                    query = query.where(ActionToken.created_at > last_push_at)
                tokens = local_session.exec(query).all()

                for token in tokens:
                    data = _record_to_dict(token)
                    _upsert_record(cloud_session, ActionToken, data, pk_field="token")
                    stats["action_tokens"] += 1

            # 9. Push UserPreferences
            with Session(local_engine, expire_on_commit=False) as local_session:
                query = select(UserPreference)
                if last_push_at:
                    query = query.where(UserPreference.created_at > last_push_at)
                prefs = local_session.exec(query).all()

                for pref in prefs:
                    data = _record_to_dict(pref)
                    _upsert_record(cloud_session, UserPreference, data)
                    stats["user_preferences"] += 1

            # 10. Push DashboardSnapshots
            with Session(local_engine, expire_on_commit=False) as local_session:
                query = select(DashboardSnapshot)
                if last_push_at:
                    query = query.where(DashboardSnapshot.created_at > last_push_at)
                snapshots = local_session.exec(query).all()

                for snapshot in snapshots:
                    data = _record_to_dict(snapshot)
                    _upsert_record(cloud_session, DashboardSnapshot, data)
                    stats["dashboard_snapshots"] += 1

            # 11. Push ContactSignals (immutable once written)
            with Session(local_engine, expire_on_commit=False) as local_session:
                query = select(ContactSignal)
                if last_push_at:
                    query = query.where(ContactSignal.assigned_at > last_push_at)
                signals = local_session.exec(query).all()

                for sig in signals:
                    data = _record_to_dict(sig)
                    _upsert_record(cloud_session, ContactSignal, data)
                    stats["contact_signals"] += 1

            # 12. Push ContactNotes
            with Session(local_engine, expire_on_commit=False) as local_session:
                query = select(ContactNote)
                if last_push_at:
                    query = query.where(ContactNote.created_at > last_push_at)
                notes = local_session.exec(query).all()

                for note in notes:
                    data = _record_to_dict(note)
                    _upsert_record(cloud_session, ContactNote, data)
                    stats["contact_notes"] += 1

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
        "Push complete: %d connections, %d queue items, %d outreach logs, %d engagement signals, "
        "%d user content, %d contact signals, %d contact notes",
        stats["connections"], stats["queue_items"], stats["outreach_logs"],
        stats["engagement_signals"], stats["user_content"],
        stats["contact_signals"], stats["contact_notes"],
    )
    return stats
