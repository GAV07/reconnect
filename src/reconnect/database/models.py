"""SQLModel definitions for Reconnect database."""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Column, Index, Text
from sqlmodel import Field, SQLModel


class UserProfile(SQLModel, table=True):
    """
    User's own profile - provides context for LLM suggestions.
    Single row table for the app user.
    """

    __tablename__ = "user_profile"

    id: int = Field(default=1, primary_key=True)
    name: str
    current_role: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    interests: Optional[str] = Field(default=None, sa_column=Column(Text))
    goals: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Flexible storage for additional context
    raw_profile: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Connection(SQLModel, table=True):
    """
    Core contact model - people the user wants to reconnect with.
    """

    __tablename__ = "connections"

    # Primary key - using UUID string for potential future sync
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)

    # Core identity fields (indexed for search)
    name: str = Field(index=True)
    email: Optional[str] = Field(default=None, index=True)
    linkedin_url: Optional[str] = Field(default=None, unique=True)

    # Current professional info (frequently queried)
    current_role: Optional[str] = Field(default=None, index=True)
    current_company: Optional[str] = Field(default=None, index=True)
    location: Optional[str] = Field(default=None, index=True)

    # Relationship metadata
    connection_source: str = Field(default="linkedin_export")
    relationship_strength: Optional[int] = Field(default=None)  # 1-5 scale
    tags: Optional[str] = Field(default=None)  # Comma-separated
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))

    # JSON columns for flexible/messy API data
    raw_enrichment: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
    )
    activity_log: Optional[list[dict[str, Any]]] = Field(
        default=None,
        sa_column=Column(JSON),
    )

    # Tracking timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    enriched_at: Optional[datetime] = Field(default=None)
    last_contacted_at: Optional[datetime] = Field(default=None)

    # LLM-generated content cache
    cached_summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    cached_summary_at: Optional[datetime] = Field(default=None)

    # Reconnection scoring (LLM-based)
    reconnect_score: Optional[float] = Field(default=None, index=True)  # 0-100 score
    score_reasoning: Optional[str] = Field(default=None, sa_column=Column(Text))
    scored_at: Optional[datetime] = Field(default=None)


# Composite indexes for common query patterns
Connection.__table_args__ = (
    Index("idx_connection_search", "name", "current_company", "current_role"),
    Index("idx_connection_freshness", "enriched_at", "updated_at"),
)


class OutreachLog(SQLModel, table=True):
    """
    Track outreach attempts and outcomes for future ML/analysis.
    """

    __tablename__ = "outreach_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    connection_id: str = Field(foreign_key="connections.id", index=True)

    channel: str  # "email", "linkedin_dm", "other"
    generated_prose: Optional[str] = Field(default=None, sa_column=Column(Text))
    sent_at: Optional[datetime] = Field(default=None)
    outcome: Optional[str] = Field(default=None)  # "replied", "no_response", "meeting_scheduled"
    outcome_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
