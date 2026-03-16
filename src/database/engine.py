"""Database engine and session management for Reconnect."""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from src.config import settings


def _create_local_engine() -> Engine:
    """Create SQLAlchemy engine for local SQLite."""
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{db_path}"
    return create_engine(
        url,
        echo=settings.debug,
        connect_args={
            "check_same_thread": False,  # Allow multi-thread access
            "timeout": 30,  # Busy timeout
        },
    )


def _create_cloud_engine() -> Engine:
    """Create SQLAlchemy engine for Supabase (PostgreSQL)."""
    if not settings.supabase_db_url:
        raise ValueError("supabase_db_url must be set for cloud mode")
    return create_engine(
        settings.supabase_db_url,
        echo=settings.debug,
        pool_pre_ping=True,
    )


def get_engine(mode: Optional[str] = None) -> Engine:
    """Create SQLAlchemy engine based on mode.

    Args:
        mode: "local" or "cloud". Defaults to settings.database_mode.
    """
    mode = mode or settings.database_mode
    if mode == "cloud":
        return _create_cloud_engine()
    return _create_local_engine()


# Global engine instance (based on DATABASE_MODE setting)
engine = get_engine()


def apply_sqlite_column_migrations(target_engine: Optional[Engine] = None):
    """Add new columns to existing SQLite tables if missing.

    SQLModel.metadata.create_all() only creates tables, not columns.
    This function issues ALTER TABLE ADD COLUMN statements for columns
    added after initial table creation. Safe to call repeatedly —
    duplicate ADD COLUMN is caught and ignored.
    """
    from sqlalchemy import text

    eng = target_engine or engine
    # Only apply to SQLite databases
    if "sqlite" not in str(eng.url):
        return

    migrations = [
        # Phase 12: enrichment extracted columns
        "ALTER TABLE connections ADD COLUMN enriched_industry TEXT",
        "ALTER TABLE connections ADD COLUMN enriched_headline TEXT",
        "ALTER TABLE connections ADD COLUMN enriched_city TEXT",
        "ALTER TABLE connections ADD COLUMN enriched_country TEXT",
        "ALTER TABLE connections ADD COLUMN enriched_school TEXT",
        "ALTER TABLE connections ADD COLUMN enriched_seniority TEXT",
        "ALTER TABLE connections ADD COLUMN education_text TEXT",
    ]

    with eng.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                # Column already exists — safe to ignore
                conn.rollback()


def init_db(target_engine: Optional[Engine] = None):
    """Create all tables.

    Args:
        target_engine: Engine to create tables on. Defaults to global engine.
    """
    # Import models to ensure they're registered
    from src.database import models  # noqa: F401

    SQLModel.metadata.create_all(target_engine or engine)
    apply_sqlite_column_migrations(target_engine)


@contextmanager
def get_session(target_engine: Optional[Engine] = None) -> Generator[Session, None, None]:
    """Provide a transactional scope around operations.

    Args:
        target_engine: Engine to use. Defaults to global engine.
    """
    session = Session(target_engine or engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
