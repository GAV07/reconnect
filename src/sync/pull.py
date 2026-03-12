"""Pull user actions from Supabase cloud DB back to local SQLite."""

import logging
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from src.database.models import (
    Connection,
    ContactNote,
    ContactSignal,
    OutreachLog,
    OutreachQueueItem,
    SyncMetadata,
    UserFeedback,
    UserPreference,
    UserProfile,
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
        "feedback_pulled": 0,
        "preferences_pulled": 0,
        "contact_signals_pulled": 0,
        "contact_notes_pulled": 0,
        "user_profile_updated": 0,
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
                "user_priority": conn.user_priority,
                "latest_signal": conn.latest_signal,
                "cadence_due_at": conn.cadence_due_at,
            })

        # 4. Pull UserFeedback entries created on cloud (e.g., via Edge Functions)
        feedback_query = select(UserFeedback)
        if last_pull_at:
            feedback_query = feedback_query.where(UserFeedback.created_at > last_pull_at)
        cloud_feedback = cloud_session.exec(feedback_query).all()

        feedback_data = []
        for fb in cloud_feedback:
            feedback_data.append({
                "id": fb.id,
                "connection_id": fb.connection_id,
                "queue_item_id": fb.queue_item_id,
                "feedback_type": fb.feedback_type,
                "rating": fb.rating,
                "text": fb.text,
                "extra_data": fb.extra_data,
                "created_at": fb.created_at,
            })

        # 5. Pull UserPreference changes from cloud
        pref_query = select(UserPreference)
        if last_pull_at:
            pref_query = pref_query.where(UserPreference.created_at > last_pull_at)
        cloud_prefs = cloud_session.exec(pref_query).all()

        pref_data = []
        for pref in cloud_prefs:
            pref_data.append({
                "id": pref.id,
                "pref_type": pref.pref_type,
                "pref_key": pref.pref_key,
                "pref_value": pref.pref_value,
                "is_active": pref.is_active,
                "created_at": pref.created_at,
            })

        # 6. Pull ContactSignal records from cloud
        signal_query = select(ContactSignal)
        if last_pull_at:
            signal_query = signal_query.where(ContactSignal.assigned_at > last_pull_at)
        cloud_signals = cloud_session.exec(signal_query).all()

        signals_data = [
            {
                "id": s.id,
                "connection_id": s.connection_id,
                "signal": s.signal,
                "signal_context": s.signal_context,
                "assigned_at": s.assigned_at,
                "assigned_by": s.assigned_by,
            }
            for s in cloud_signals
        ]

        # 7. Pull ContactNote records from cloud
        note_query = select(ContactNote)
        if last_pull_at:
            note_query = note_query.where(ContactNote.created_at > last_pull_at)
        cloud_notes = cloud_session.exec(note_query).all()

        notes_data = [
            {
                "id": n.id,
                "connection_id": n.connection_id,
                "note_text": n.note_text,
                "created_at": n.created_at,
                "updated_at": n.updated_at,
            }
            for n in cloud_notes
        ]

        # 8. Pull UserProfile goals fields from cloud
        profile_data = None
        cloud_profile = cloud_session.get(UserProfile, 1)
        if cloud_profile:
            profile_data = {
                "id": cloud_profile.id,
                "current_projects": cloud_profile.current_projects,
                "goals_structured": cloud_profile.goals_structured,
                "updated_at": cloud_profile.updated_at,
            }

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

            # Apply last_contacted_at, user_priority, latest_signal, and cadence_due_at updates
            for contact_data in contacts_data:
                local_conn = local_session.get(Connection, contact_data["id"])
                if local_conn:
                    updated = False
                    cloud_ts = contact_data["last_contacted_at"]
                    local_ts = local_conn.last_contacted_at
                    if local_ts is None or (cloud_ts and cloud_ts > local_ts):
                        local_conn.last_contacted_at = cloud_ts
                        updated = True
                    # user_priority: cloud wins (set by Edge Functions)
                    cloud_priority = contact_data.get("user_priority")
                    if cloud_priority and cloud_priority != local_conn.user_priority:
                        local_conn.user_priority = cloud_priority
                        updated = True
                    # latest_signal: cloud wins (assigned by PWA user)
                    cloud_signal = contact_data.get("latest_signal")
                    if cloud_signal and cloud_signal != local_conn.latest_signal:
                        local_conn.latest_signal = cloud_signal
                        updated = True
                    # cadence_due_at: cloud wins
                    cloud_cadence = contact_data.get("cadence_due_at")
                    if cloud_cadence and cloud_cadence != local_conn.cadence_due_at:
                        local_conn.cadence_due_at = cloud_cadence
                        updated = True
                    if updated:
                        local_session.add(local_conn)
                        stats["contacts_updated"] += 1

            # Apply feedback entries (insert if not exists)
            for fb_data in feedback_data:
                existing = local_session.get(UserFeedback, fb_data["id"])
                if not existing:
                    fb_obj = UserFeedback(**fb_data)
                    local_session.add(fb_obj)
                    stats["feedback_pulled"] += 1

            # Apply preference entries (insert if not exists)
            for pref_data_item in pref_data:
                existing = local_session.get(UserPreference, pref_data_item["id"])
                if not existing:
                    pref_obj = UserPreference(**pref_data_item)
                    local_session.add(pref_obj)
                    stats["preferences_pulled"] += 1

            # Apply contact signal records (insert if not exists)
            for sig_data in signals_data:
                existing = local_session.get(ContactSignal, sig_data["id"])
                if not existing:
                    local_session.add(ContactSignal(**sig_data))
                    stats["contact_signals_pulled"] += 1

            # Apply contact note records (insert if not exists, update if newer)
            for note_data in notes_data:
                existing = local_session.get(ContactNote, note_data["id"])
                if not existing:
                    local_session.add(ContactNote(**note_data))
                    stats["contact_notes_pulled"] += 1
                elif note_data.get("updated_at") and existing.updated_at and note_data["updated_at"] > existing.updated_at:
                    existing.note_text = note_data["note_text"]
                    existing.updated_at = note_data["updated_at"]
                    local_session.add(existing)
                    stats["contact_notes_pulled"] += 1

            # 8. Apply user_profile goals (cloud wins if cloud is newer)
            if profile_data:
                local_profile = local_session.get(UserProfile, 1)
                if local_profile:
                    cloud_ts = profile_data.get("updated_at")
                    local_ts = local_profile.updated_at
                    if cloud_ts and (local_ts is None or cloud_ts > local_ts):
                        local_profile.current_projects = profile_data["current_projects"]
                        local_profile.goals_structured = profile_data["goals_structured"]
                        # Do NOT update local_profile.updated_at — avoids push sync loop (research pitfall 5)
                        local_session.add(local_profile)
                        stats["user_profile_updated"] = 1

            # Update sync metadata
            meta = _get_sync_metadata(local_session)
            meta.last_pull_at = datetime.utcnow()
            meta.last_pull_actions = (
                stats["queue_items_updated"]
                + stats["outreach_logs_pulled"]
                + stats["contacts_updated"]
                + stats["feedback_pulled"]
                + stats["preferences_pulled"]
                + stats["contact_signals_pulled"]
                + stats["contact_notes_pulled"]
                + stats["user_profile_updated"]
            )
            local_session.add(meta)

            local_session.commit()

        except Exception:
            local_session.rollback()
            raise

    logger.info(
        "Pull complete: %d queue items, %d logs, %d contacts, %d feedback, %d preferences, %d signals, %d notes",
        stats["queue_items_updated"], stats["outreach_logs_pulled"], stats["contacts_updated"],
        stats["feedback_pulled"], stats["preferences_pulled"],
        stats["contact_signals_pulled"], stats["contact_notes_pulled"],
    )
    return stats
