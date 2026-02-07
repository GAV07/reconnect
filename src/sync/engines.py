"""Explicit local/cloud engine helpers for sync operations.

These always return the requested engine type regardless of DATABASE_MODE,
since sync needs to talk to both databases simultaneously.
"""

from sqlalchemy import Engine

from src.database.engine import _create_cloud_engine, _create_local_engine


def get_local_engine() -> Engine:
    """Always returns a local SQLite engine."""
    return _create_local_engine()


def get_cloud_engine() -> Engine:
    """Always returns a Supabase PostgreSQL engine."""
    return _create_cloud_engine()
