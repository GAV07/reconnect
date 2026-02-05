"""Database engine and session management for Reconnect."""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlmodel import Session, SQLModel, create_engine

from src.config import settings


def get_database_url() -> str:
    """Construct SQLite database URL."""
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


def get_engine():
    """Create SQLAlchemy engine with SQLite optimizations."""
    engine = create_engine(
        get_database_url(),
        echo=settings.debug,
        connect_args={
            "check_same_thread": False,  # Required for Streamlit
            "timeout": 30,  # Busy timeout
        },
    )
    return engine


# Global engine instance
engine = get_engine()


def init_db():
    """Create all tables."""
    # Import models to ensure they're registered
    from src.database import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional scope around operations."""
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
