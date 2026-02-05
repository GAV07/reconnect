"""Action buttons component for Reconnect UI."""

import json
import urllib.parse
from datetime import datetime

import streamlit as st

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection
from src.ingestion.apify_client import update_connection_activity
from src.llm.prose import ProseResult, get_or_generate_prose
from src.llm.scoring import score_connection


def get_drafts_cache() -> dict:
    """Get or create the drafts cache in session state."""
    if "outreach_drafts" not in st.session_state:
        st.session_state.outreach_drafts = {}
    return st.session_state.outreach_drafts


def save_draft(connection_id: str, prose: ProseResult, connection_name: str):
    """Save a generated draft to session state and database."""
    drafts = get_drafts_cache()
    drafts[connection_id] = {
        "prose": prose,
        "connection_name": connection_name,
        "generated_at": datetime.utcnow().isoformat(),
    }

    # Also save to database cache for persistence
    with get_session() as session:
        connection = session.get(Connection, connection_id)
        if connection:
            connection.cached_summary = prose.to_json()
            connection.cached_summary_at = datetime.utcnow()
            session.add(connection)


def get_draft(connection_id: str) -> ProseResult | None:
    """Get a draft from session state or database."""
    # First check session state
    drafts = get_drafts_cache()
    if connection_id in drafts:
        return drafts[connection_id]["prose"]

    # Then check database cache
    with get_session() as session:
        connection = session.get(Connection, connection_id)
        if connection and connection.cached_summary:
            try:
                prose = ProseResult.from_json(connection.cached_summary)
                # Also save to session state for quick access
                drafts[connection_id] = {
                    "prose": prose,
                    "connection_name": connection.name,
                    "generated_at": connection.cached_summary_at.isoformat() if connection.cached_summary_at else None,
                }
                return prose
            except (json.JSONDecodeError, KeyError):
                pass

    return None


def create_mailto_link(email: str, subject: str = "", body: str = "") -> str:
    """Create a mailto: link with pre-filled subject and body."""
    params = {}
    if subject:
        params["subject"] = subject
    if body:
        params["body"] = body

    query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"mailto:{email}?{query_string}"


def create_linkedin_dm_url(linkedin_url: str) -> str:
    """
    Create URL to LinkedIn profile (for manual DM).

    Note: LinkedIn doesn't support deep linking directly to DM with pre-filled text.
    """
    return linkedin_url


def render_action_buttons(connection_id: str):
    """Render action buttons for outreach."""
    with get_session() as session:
        connection = session.get(Connection, connection_id)
        if not connection:
            return
        # Load attributes before session closes
        conn_name = connection.name
        conn_email = connection.email
        conn_linkedin_url = connection.linkedin_url
        conn_enriched = connection.enriched_at is not None
        conn_scored = connection.reconnect_score is not None

    st.write("**Actions**")

    # Check if user has goals set (needed for scoring)
    with get_session() as session:
        from src.database.models import UserProfile
        user_profile = session.get(UserProfile, 1)
        has_goals = user_profile and user_profile.goals

    col1, col2, col3 = st.columns(3)

    with col1:
        enrich_label = "🔄 Re-enrich" if conn_enriched else "🔄 Enrich"
        if st.button(enrich_label, use_container_width=True, key="btn_enrich"):
            with st.spinner("Fetching LinkedIn data..."):
                try:
                    if update_connection_activity(connection_id):
                        # Also score if user has goals
                        if has_goals:
                            score_connection(connection_id)
                        st.success("Profile enriched & scored!")
                        st.rerun()
                    else:
                        st.error("Failed to fetch. Check LinkedIn URL.")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    with col2:
        score_label = "🎯 Re-score" if conn_scored else "🎯 Score"
        score_disabled = not conn_enriched or not has_goals
        score_help = None
        if not conn_enriched:
            score_help = "Enrich first"
        elif not has_goals:
            score_help = "Set goals in Settings"

        if st.button(score_label, use_container_width=True, key="btn_score",
                     disabled=score_disabled, help=score_help):
            with st.spinner("Scoring connection..."):
                try:
                    result = score_connection(connection_id)
                    if result:
                        st.success(f"Scored: {int(result.score)}/100")
                        st.rerun()
                    else:
                        st.error("Failed to score")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    with col3:
        generate_disabled = not settings.openai_api_key
        help_text = "Set OPENAI_API_KEY in .env" if generate_disabled else None

        # Check if we have a cached draft
        existing_draft = get_draft(connection_id)
        gen_label = "✨ Regenerate" if existing_draft else "✨ Generate Outreach"

        if st.button(
            gen_label,
            use_container_width=True,
            key="btn_generate",
            disabled=generate_disabled,
            help=help_text,
        ):
            with st.spinner("Generating personalized message..."):
                try:
                    result = get_or_generate_prose(connection_id, force_refresh=True)
                    save_draft(connection_id, result, conn_name)
                except Exception as e:
                    st.error(f"Error generating prose: {str(e)}")

    # Display generated prose - check for this connection specifically
    prose = get_draft(connection_id)
    if prose:

        st.divider()

        st.write("**Summary**")
        st.write(prose.summary)

        st.write("**Why Reach Out**")
        st.info(prose.reason_to_reach_out)

        st.write("**Suggested Message**")
        message_text = st.text_area(
            "Edit message:",
            value=prose.suggested_message,
            height=150,
            key=f"editable_message_{connection_id}",
            label_visibility="collapsed",
        )

        st.write("**Talking Points**")
        for point in prose.talking_points:
            st.markdown(f"- {point}")

        st.divider()

        # Action buttons with the message
        col_email, col_linkedin = st.columns(2)

        with col_email:
            if conn_email:
                mailto_link = create_mailto_link(
                    conn_email,
                    subject=f"Reconnecting - {conn_name.split()[0]}",
                    body=message_text,
                )
                st.markdown(
                    f'<a href="{mailto_link}" target="_blank">'
                    f'<button style="width:100%;padding:0.5rem;cursor:pointer;">'
                    f"📧 Open Email</button></a>",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No email available")

        with col_linkedin:
            if conn_linkedin_url:
                st.markdown(
                    f'<a href="{conn_linkedin_url}" target="_blank">'
                    f'<button style="width:100%;padding:0.5rem;cursor:pointer;">'
                    f"💬 Open LinkedIn</button></a>",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No LinkedIn URL")

        # Copy message button
        st.divider()
        if st.button("📋 Copy Message to Clipboard", use_container_width=True, key=f"copy_{connection_id}"):
            st.code(message_text, language=None)
            st.caption("Select and copy the message above (Ctrl+C / Cmd+C)")


def render_drafts_sidebar():
    """Render a list of all saved drafts in the sidebar."""
    drafts = get_drafts_cache()

    if not drafts:
        return

    st.subheader("📝 Drafts")
    st.caption(f"{len(drafts)} saved outreach messages")

    for conn_id, draft_data in list(drafts.items()):
        conn_name = draft_data.get("connection_name", "Unknown")

        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button(f"📄 {conn_name}", key=f"draft_{conn_id}", use_container_width=True):
                st.session_state.selected_connection_id = conn_id
                st.session_state.show_detail_dialog = True
                st.rerun()
        with col2:
            if st.button("🗑️", key=f"del_draft_{conn_id}"):
                del drafts[conn_id]
                st.rerun()

    st.divider()
