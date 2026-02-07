"""Sync orchestrator — runs push then pull in sequence."""

import logging
from datetime import datetime
from typing import Any

from sqlmodel import Session

from src.database.models import SyncMetadata
from src.sync.engines import get_local_engine
from src.sync.pull import pull_from_cloud
from src.sync.push import push_to_cloud

logger = logging.getLogger(__name__)


def run_sync() -> dict[str, Any]:
    """Run a full sync cycle: push local results to cloud, then pull actions back.

    Push runs first to ensure the cloud has the latest pipeline results
    before pulling back any user actions taken against previous data.

    Returns:
        Dict with combined push and pull stats.
    """
    result: dict[str, Any] = {
        "push": None,
        "pull": None,
        "error": None,
    }

    try:
        logger.info("Starting sync: push to cloud...")
        result["push"] = push_to_cloud()

        logger.info("Starting sync: pull from cloud...")
        result["pull"] = pull_from_cloud()

        logger.info("Sync complete.")

    except Exception as e:
        result["error"] = str(e)
        logger.error("Sync failed: %s", e)

        # Record error in sync metadata
        try:
            local_engine = get_local_engine()
            with Session(local_engine, expire_on_commit=False) as session:
                meta = session.get(SyncMetadata, 1)
                if not meta:
                    meta = SyncMetadata(id=1)
                meta.last_error = str(e)
                meta.last_error_at = datetime.utcnow()
                session.add(meta)
                session.commit()
        except Exception:
            logger.error("Failed to record sync error in metadata")

        raise

    return result
