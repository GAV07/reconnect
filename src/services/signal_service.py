"""Signal service — canonical single source of truth for triage signal behavior.

Defines all 7 triage signals with their cadence_days, queue_status, and
priority_boost values. These values must NOT be duplicated elsewhere in Python;
the PWA mirrors them as a JS const derived from this source.

Signal meanings:
  WARM_LEAD     — Hot lead, follow up soon (7-day cadence)
  NURTURE       — Worth maintaining slowly (21-day cadence)
  VALUE_DROP    — Share value, reappear in 14 days
  SYNERGY       — Mutual benefit opportunity (14-day cadence)
  RECONNECT     — Re-engage a lapsed contact (14-day cadence)
  FUTURE_PIVOT  — Not now, but later (60-day cadence)
  ARCHIVE       — Permanently stop re-queuing (sets user_priority = 'never')
"""

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import select

from src.database.engine import get_session
from src.database.models import Connection, ContactSignal

logger = logging.getLogger(__name__)


@dataclass
class SignalAction:
    """Defines the behavior for a single triage signal."""

    cadence_days: Optional[int]  # None means never re-queue (ARCHIVE)
    queue_status: str  # "approved" | "pending_review" | "skipped"
    priority_boost: int  # Points added to priority_score when signal applied
    description: str


# ---------------------------------------------------------------------------
# Canonical signal definitions — single source of truth
# Values locked per 07-CONTEXT.md implementation decisions
# ---------------------------------------------------------------------------

SIGNAL_ACTIONS: dict[str, SignalAction] = {
    "WARM_LEAD": SignalAction(
        cadence_days=7,
        queue_status="approved",
        priority_boost=15,
        description="Hot lead -- follow up in 7 days",
    ),
    "NURTURE": SignalAction(
        cadence_days=21,
        queue_status="pending_review",
        priority_boost=0,
        description="Worth nurturing -- 21-day cadence",
    ),
    "VALUE_DROP": SignalAction(
        cadence_days=14,
        queue_status="skipped",
        priority_boost=0,
        description="Share value -- reappear in 14 days",
    ),
    "SYNERGY": SignalAction(
        cadence_days=14,
        queue_status="approved",
        priority_boost=10,
        description="Mutual benefit -- follow up in 14 days",
    ),
    "RECONNECT": SignalAction(
        cadence_days=14,
        queue_status="approved",
        priority_boost=5,
        description="Reconnect -- follow up in 14 days",
    ),
    "FUTURE_PIVOT": SignalAction(
        cadence_days=60,
        queue_status="pending_review",
        priority_boost=0,
        description="Potential later -- 60-day cadence",
    ),
    "ARCHIVE": SignalAction(
        cadence_days=None,
        queue_status="skipped",
        priority_boost=0,
        description="Archive -- never re-queue",
    ),
}


def apply_signal(
    connection_id: str,
    signal: str,
    signal_context: Optional[str] = None,
    assigned_by: str = "user",
) -> ContactSignal:
    """Apply a triage signal to a contact.

    Creates a ContactSignal record and updates Connection.latest_signal and
    Connection.cadence_due_at. For ARCHIVE, also sets user_priority = 'never'.

    Args:
        connection_id: UUID string of the target Connection
        signal: One of the 7 canonical signal names in SIGNAL_ACTIONS
        signal_context: Optional freeform context note about why this signal was applied
        assigned_by: Source of the assignment — "user" | "system" | "pipeline"

    Returns:
        The newly created ContactSignal record

    Raises:
        ValueError: If signal is not a known key in SIGNAL_ACTIONS
    """
    if signal not in SIGNAL_ACTIONS:
        raise ValueError(
            f"Unknown signal '{signal}'. Valid signals: {list(SIGNAL_ACTIONS.keys())}"
        )

    action = SIGNAL_ACTIONS[signal]
    now = datetime.utcnow()

    # Compute cadence_due_at: now + cadence_days for non-ARCHIVE, None for ARCHIVE
    if action.cadence_days is not None:
        cadence_due_at = now + timedelta(days=action.cadence_days)
    else:
        cadence_due_at = None

    with get_session() as session:
        # Create the signal record
        contact_signal = ContactSignal(
            connection_id=connection_id,
            signal=signal,
            signal_context=signal_context,
            assigned_at=now,
            assigned_by=assigned_by,
        )
        session.add(contact_signal)

        # Update the connection's latest signal and cadence
        connection = session.get(Connection, connection_id)
        if connection is not None:
            connection.latest_signal = signal
            connection.cadence_due_at = cadence_due_at

            # ARCHIVE permanently stops re-queuing
            if signal == "ARCHIVE":
                connection.user_priority = "never"

            session.add(connection)

        session.commit()
        session.refresh(contact_signal)

    logger.info(
        "Signal applied: connection=%s signal=%s assigned_by=%s cadence_due_at=%s",
        connection_id,
        signal,
        assigned_by,
        cadence_due_at,
    )
    return contact_signal


def backfill_skipped_signals() -> dict[str, int]:
    """Backfill signal values on existing skipped OutreachQueueItems.

    Maps existing skipped items to the most appropriate signal based on
    why they were skipped:
      - "Queue reset" or "Auto-expired" in skip_reason -> RECONNECT
        (they timed out, not intentionally dismissed)
      - Explicit user skip (reviewed_at set, no auto-reason) -> FUTURE_PIVOT
        (conservative: don't archive, but don't re-queue soon either)
      - Already has a signal -> skip (count as already_set)

    Returns:
        dict with counts: {"reconnect": int, "future_pivot": int, "already_set": int}
    """
    # Lazy import to avoid potential circular dependency issues at module load time
    from src.database.models import OutreachQueueItem

    counts = {"reconnect": 0, "future_pivot": 0, "already_set": 0}
    auto_reasons = ("Queue reset", "Auto-expired")

    with get_session() as session:
        skipped_items = session.exec(
            select(OutreachQueueItem).where(OutreachQueueItem.status == "skipped")
        ).all()

        for item in skipped_items:
            # Skip items that already have a signal assigned
            if item.signal is not None:
                counts["already_set"] += 1
                continue

            skip_reason = item.skip_reason or ""
            is_auto_skip = any(reason in skip_reason for reason in auto_reasons)

            if is_auto_skip:
                item.signal = "RECONNECT"
                session.add(item)
                counts["reconnect"] += 1
            elif item.reviewed_at is not None:
                # Explicit user skip: reviewed but not auto-expired
                item.signal = "FUTURE_PIVOT"
                session.add(item)
                counts["future_pivot"] += 1

        session.commit()

    logger.info(
        "Backfill complete: reconnect=%d future_pivot=%d already_set=%d",
        counts["reconnect"],
        counts["future_pivot"],
        counts["already_set"],
    )
    return counts
