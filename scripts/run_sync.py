"""CLI script for manual/cron cloud sync.

Usage:
    python scripts/run_sync.py              # Full sync (push + pull)
    python scripts/run_sync.py --push-only  # Only push to cloud
    python scripts/run_sync.py --pull-only  # Only pull from cloud
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Sync Reconnect data with Supabase cloud")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--push-only", action="store_true", help="Only push local data to cloud")
    group.add_argument("--pull-only", action="store_true", help="Only pull cloud actions to local")
    args = parser.parse_args()

    from src.config import settings

    if not settings.supabase_db_url:
        logger.error("SUPABASE_DB_URL must be set in .env or environment")
        sys.exit(1)

    try:
        if args.push_only:
            from src.sync.push import push_to_cloud

            logger.info("Running push-only sync...")
            stats = push_to_cloud()
            logger.info("Push stats: %s", stats)

        elif args.pull_only:
            from src.sync.pull import pull_from_cloud

            logger.info("Running pull-only sync...")
            stats = pull_from_cloud()
            logger.info("Pull stats: %s", stats)

        else:
            from src.sync.runner import run_sync

            logger.info("Running full sync (push + pull)...")
            result = run_sync()
            logger.info("Push stats: %s", result["push"])
            logger.info("Pull stats: %s", result["pull"])

    except Exception as e:
        logger.error("Sync failed: %s", e)
        sys.exit(1)

    logger.info("Done.")


if __name__ == "__main__":
    main()
