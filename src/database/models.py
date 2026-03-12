"""SQLModel definitions for Reconnect database."""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Column, Index, Text
from sqlmodel import Field, SQLModel


def get_enrichment_data(connection: "Connection") -> dict:
    """Unwrap enrichment data from raw_enrichment.

    RapidAPI responses nest profile fields under a ``"data"`` key.  Older
    records or other providers may store fields at the top level.  This
    helper returns the inner dict so callers always get flat field access
    (e.g. ``data.get("headline")``).
    """
    raw = connection.raw_enrichment or {}
    if "data" in raw and isinstance(raw["data"], dict):
        return raw["data"]
    return raw


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

    # Inferred profile data (from LinkedIn dump analysis)
    inferred_industry: Optional[str] = None
    inferred_seniority: Optional[str] = None  # executive/senior/mid/entry
    inferred_expertise: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    inferred_interests: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    profile_auto_updated_at: Optional[datetime] = None

    # LinkedIn profile data (from Profile.csv)
    headline: Optional[str] = Field(default=None, sa_column=Column(Text))
    about_summary: Optional[str] = Field(default=None, sa_column=Column(Text))

    # User persona (from posts/shares analysis)
    posting_themes: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    public_persona_summary: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Signal foundation (v1.2)
    current_projects: Optional[str] = Field(default=None, sa_column=Column(Text))
    goals_structured: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

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

    # Reconnection scoring (LLM-based, post-enrichment)
    reconnect_score: Optional[float] = Field(default=None, index=True)  # 0-100 score
    score_reasoning: Optional[str] = Field(default=None, sa_column=Column(Text))
    scored_at: Optional[datetime] = Field(default=None)

    # Message history (from LinkedIn Messages.csv)
    last_message_date: Optional[datetime] = Field(default=None, index=True)
    message_count: int = Field(default=0)
    initiated_by: Optional[str] = None  # "user" | "contact"
    conversation_summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    conversation_status: Optional[str] = None  # "active" | "stale" | "never"

    # Pre-enrichment scoring (before Apify enrichment)
    pre_score: Optional[float] = Field(default=None, index=True)  # 0-100
    pre_score_tier: Optional[int] = None  # 1=enrich, 2=maybe, 3=skip
    pre_scored_at: Optional[datetime] = None

    # Import tracking
    import_batch_id: Optional[str] = Field(default=None, index=True)
    is_new_connection: bool = Field(default=False)
    connected_on: Optional[datetime] = None

    # Engagement metrics (from reactions, comments, endorsements)
    engagement_score: Optional[float] = Field(default=None, index=True)  # 0-100 aggregate
    last_engagement_date: Optional[datetime] = None
    engagement_direction: Optional[str] = None  # "user_to_contact" | "contact_to_user" | "mutual"
    endorsement_count: int = Field(default=0)
    has_recommendation: bool = Field(default=False)

    # User priority and data completeness (PWA overhaul)
    user_priority: Optional[str] = None  # "always" | "never" | NULL
    data_completeness_score: Optional[float] = None  # 0-100
    missing_data_fields: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))

    # Signal foundation (v1.2)
    latest_signal: Optional[str] = None  # Last applied signal name
    cadence_due_at: Optional[datetime] = Field(default=None)  # Next re-queue date


# Composite indexes for common query patterns
Connection.__table_args__ = (
    Index("idx_connection_search", "name", "current_company", "current_role"),
    Index("idx_connection_freshness", "enriched_at", "updated_at"),
    Index("idx_connection_engagement", "engagement_score", "last_engagement_date"),
)


class EngagementSignal(SQLModel, table=True):
    """
    Track engagement signals between user and connections.
    Captures reactions, comments, endorsements, and recommendations.
    """

    __tablename__ = "engagement_signals"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    connection_id: Optional[str] = Field(default=None, foreign_key="connections.id", index=True)
    connection_name: str  # Name for matching when connection_id unknown

    signal_type: str  # "reaction" | "comment" | "endorsement_given" | "endorsement_received" | "recommendation_given" | "recommendation_received"
    signal_strength: int = Field(default=1)  # 1-5 scale
    content_snippet: Optional[str] = Field(default=None, sa_column=Column(Text))
    signal_date: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContactSignal(SQLModel, table=True):
    """
    Records when a user assigns a triage signal to a contact.
    Canonical signal names: WARM_LEAD | NURTURE | VALUE_DROP | SYNERGY |
    RECONNECT | FUTURE_PIVOT | ARCHIVE
    """

    __tablename__ = "contact_signals"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    connection_id: str = Field(foreign_key="connections.id", index=True)
    signal: str  # Required — one of the 7 canonical signal names
    signal_context: Optional[str] = Field(default=None, sa_column=Column(Text))
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_by: str = Field(default="user")  # "user" | "system" | "pipeline"


class ContactNote(SQLModel, table=True):
    """
    Timestamped notes attached to a contact.
    Complementary to connections.notes (free-form); provides queryable history.
    """

    __tablename__ = "contact_notes"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    connection_id: str = Field(foreign_key="connections.id", index=True)
    note_text: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserContent(SQLModel, table=True):
    """
    User's own LinkedIn content (posts, shares, articles).
    Used for persona extraction and theme analysis.
    """

    __tablename__ = "user_content"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    content_type: str  # "post" | "article" | "share"
    content_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    topics: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    posted_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


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


class OutreachQueueItem(SQLModel, table=True):
    """
    Queue items for review - contacts to reach out to.
    """

    __tablename__ = "outreach_queue"

    id: Optional[int] = Field(default=None, primary_key=True)
    connection_id: str = Field(foreign_key="connections.id", index=True)

    channel: str  # "email" | "linkedin"
    draft_message: Optional[str] = Field(default=None, sa_column=Column(Text))
    draft_subject: Optional[str] = None  # For email

    # Status workflow: pending_review -> approved/skipped -> sent
    status: str = Field(default="pending_review", index=True)
    # pending_review, approved, skipped, sent, failed

    priority_score: Optional[float] = None  # For sorting queue
    skip_reason: Optional[str] = None
    why_today: Optional[str] = None  # Time-sensitive reason for outreach

    # Signal foundation (v1.2)
    signal: Optional[str] = None  # Applied signal name (WARM_LEAD, NURTURE, etc.)
    signal_context: Optional[str] = Field(default=None, sa_column=Column(Text))
    mini_key_factors: Optional[str] = Field(default=None, sa_column=Column(Text))

    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None


class ImportBatch(SQLModel, table=True):
    """
    Track imports for diffing and history.
    """

    __tablename__ = "import_batches"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)

    source_type: str  # "linkedin_csv" | "linkedin_dump" | "manual"
    file_hash: Optional[str] = None  # SHA256 of imported file(s)

    # Stats
    total_rows: int = 0
    imported_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0

    # New connections detected in this batch
    new_connection_ids: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class GmailCredentials(SQLModel, table=True):
    """
    OAuth tokens for Gmail integration.
    Single row table for the app user.
    """

    __tablename__ = "gmail_credentials"

    id: int = Field(default=1, primary_key=True)

    access_token: Optional[str] = Field(default=None, sa_column=Column(Text))
    refresh_token: Optional[str] = Field(default=None, sa_column=Column(Text))
    token_uri: str = "https://oauth2.googleapis.com/token"
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    scopes: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))

    expiry: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class SyncMetadata(SQLModel, table=True):
    """
    Singleton table to track cloud sync state.
    Always id=1.
    """

    __tablename__ = "sync_metadata"

    id: int = Field(default=1, primary_key=True)

    last_push_at: Optional[datetime] = None
    last_pull_at: Optional[datetime] = None
    last_push_connections: int = Field(default=0)
    last_push_queue_items: int = Field(default=0)
    last_pull_actions: int = Field(default=0)

    last_error: Optional[str] = Field(default=None, sa_column=Column(Text))
    last_error_at: Optional[datetime] = None


class PipelineRun(SQLModel, table=True):
    """
    Track pipeline executions for monitoring and debugging.
    """

    __tablename__ = "pipeline_runs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)

    run_type: str  # "daily" | "manual" | "import_only"
    status: str = Field(default="running", index=True)  # running, completed, failed

    # Input parameters
    input_params: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Step results
    steps_completed: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    step_results: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Error tracking
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))
    error_step: Optional[str] = None

    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class ActionToken(SQLModel, table=True):
    """One-time-use tokens for email action links."""

    __tablename__ = "action_tokens"

    token: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    action: str  # "approve", "skip", "snooze", "feedback"
    queue_item_id: Optional[int] = Field(default=None, foreign_key="outreach_queue.id")
    connection_id: Optional[str] = Field(default=None, foreign_key="connections.id")
    payload: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    used: bool = Field(default=False)
    used_at: Optional[datetime] = None
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserFeedback(SQLModel, table=True):
    """User feedback signals for learning from behavior."""

    __tablename__ = "user_feedback"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    connection_id: Optional[str] = Field(default=None, foreign_key="connections.id")
    queue_item_id: Optional[int] = Field(default=None, foreign_key="outreach_queue.id")
    feedback_type: str  # "suggestion_quality", "outcome", "preference", "digest_rating"
    rating: Optional[int] = None  # 1-5
    text: Optional[str] = Field(default=None, sa_column=Column(Text))
    extra_data: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column("metadata", JSON)
    )  # Maps to "metadata" column in DB but avoids SQLAlchemy reserved name
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserPreference(SQLModel, table=True):
    """User preferences for scoring and suggestions."""

    __tablename__ = "user_preferences"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    pref_type: str  # "industry_interest", "company_interest", "role_interest", "scoring_weight"
    pref_key: str
    pref_value: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DashboardSnapshot(SQLModel, table=True):
    """Pipeline-computed dashboard data pushed to Supabase for PWA access."""

    __tablename__ = "dashboard_snapshots"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    snapshot_type: str  # "daily", "weekly"
    snapshot_data: dict[str, Any] = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
