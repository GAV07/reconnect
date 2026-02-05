"""Search and filter components for Reconnect UI."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import streamlit as st
from sqlmodel import col, or_, select

from src.database.engine import get_session
from src.database.models import Connection


@dataclass
class SearchFilters:
    """Container for search filter values."""

    query: str = ""
    company: Optional[str] = None
    tags: Optional[str] = None
    stale_only: bool = False  # No contact in 6+ months
    not_enriched: bool = False  # Never been enriched
    scored_only: bool = False  # Only show scored contacts
    sort_by: str = "name"  # "name", "score", "enriched"


def render_search_filters() -> SearchFilters:
    """Render search filter UI and return filter values."""
    query = st.text_input(
        "Search",
        placeholder="Name, role, or company...",
        key="search_query",
    )

    # Get unique companies for dropdown
    with get_session() as session:
        companies = session.exec(
            select(Connection.current_company)
            .where(Connection.current_company.isnot(None))
            .where(Connection.current_company != "")
            .distinct()
        ).all()

    company_options = ["All"] + sorted([c for c in companies if c])
    company = st.selectbox(
        "Company",
        options=company_options,
        key="filter_company",
    )

    stale_only = st.checkbox(
        "Stale contacts only (6+ months)",
        key="filter_stale",
    )

    not_enriched = st.checkbox(
        "Not enriched yet",
        key="filter_not_enriched",
        help="Show only contacts that haven't been enriched with LinkedIn activity",
    )

    scored_only = st.checkbox(
        "Scored only",
        key="filter_scored_only",
        help="Show only contacts that have been scored by AI",
    )

    sort_by = st.selectbox(
        "Sort by",
        options=["name", "score", "enriched"],
        format_func=lambda x: {
            "name": "Name (A-Z)",
            "score": "Score (highest first)",
            "enriched": "Recently enriched",
        }[x],
        key="sort_by",
    )

    return SearchFilters(
        query=query,
        company=company if company != "All" else None,
        stale_only=stale_only,
        not_enriched=not_enriched,
        scored_only=scored_only,
        sort_by=sort_by,
    )


def search_connections(filters: SearchFilters, limit: int = 50) -> list[Connection]:
    """Execute search query with filters."""
    with get_session() as session:
        query = select(Connection)

        # Text search
        if filters.query:
            search_term = f"%{filters.query}%"
            query = query.where(
                or_(
                    col(Connection.name).ilike(search_term),
                    col(Connection.current_role).ilike(search_term),
                    col(Connection.current_company).ilike(search_term),
                )
            )

        # Company filter
        if filters.company:
            query = query.where(Connection.current_company == filters.company)

        # Stale filter (no contact in 6+ months)
        if filters.stale_only:
            six_months_ago = datetime.utcnow() - timedelta(days=180)
            query = query.where(
                or_(
                    Connection.last_contacted_at.is_(None),
                    Connection.last_contacted_at < six_months_ago,
                )
            )

        # Not enriched filter
        if filters.not_enriched:
            query = query.where(Connection.enriched_at.is_(None))

        # Scored only filter
        if filters.scored_only:
            query = query.where(Connection.reconnect_score.isnot(None))

        # Sorting
        if filters.sort_by == "score":
            # Sort by score descending, nulls last
            query = query.order_by(Connection.reconnect_score.desc().nullslast())
        elif filters.sort_by == "enriched":
            query = query.order_by(Connection.enriched_at.desc().nullslast())
        else:
            query = query.order_by(Connection.name)

        query = query.limit(limit)

        results = session.exec(query).all()

        # Explicitly access all attributes used in UI to load them before session closes
        # This prevents DetachedInstanceError when accessing these outside the session
        for conn in results:
            _ = conn.id
            _ = conn.name
            _ = conn.current_role
            _ = conn.current_company
            _ = conn.enriched_at
            _ = conn.reconnect_score

        return list(results)
