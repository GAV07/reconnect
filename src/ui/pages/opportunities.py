"""Opportunity matching UI — find contacts for specific needs."""

import streamlit as st

from src.database.engine import get_session
from src.database.models import Connection, UserProfile
from src.llm.opportunity_match import find_matches
from src.pipeline.queue_generator import determine_channel, generate_queue_item
from src.ui.components.detail import render_connection_detail


def render_opportunities_page():
    """Render the opportunity matching page."""
    st.title("Find Contacts")
    st.caption("Describe what you need and we'll match contacts from your network")

    request = st.text_area(
        "What are you looking for?",
        placeholder="e.g. someone in venture capital, edtech founders in Miami, "
        "intro to someone at Google working on AI...",
        height=100,
    )

    col_btn, col_limit = st.columns([2, 1])
    with col_limit:
        limit = st.number_input("Max results", min_value=1, max_value=50, value=10)
    with col_btn:
        st.write("")  # spacer
        search_clicked = st.button(
            "Find Matches", use_container_width=True, type="primary"
        )

    if search_clicked and request.strip():
        with st.spinner("Searching your network..."):
            matches = find_matches(request.strip(), limit=limit)
        st.session_state.opp_matches = matches
        st.session_state.opp_request = request.strip()

    # Render results
    matches = st.session_state.get("opp_matches")

    if matches is not None and len(matches) == 0:
        st.info("No matches found. Try broadening your request.")
    elif matches:
        st.subheader(f"{len(matches)} matches")

        for i, match in enumerate(matches):
            with st.container():
                cols = st.columns([0.6, 2.5, 2, 1.2])

                with cols[0]:
                    st.markdown(f"**{match.score}**")

                with cols[1]:
                    st.markdown(f"**{match.name}**")
                    if match.connection.current_role:
                        role_text = match.connection.current_role
                        if match.connection.current_company:
                            role_text += f" @ {match.connection.current_company}"
                        st.caption(role_text)

                with cols[2]:
                    if match.connection.location:
                        st.caption(match.connection.location)

                with cols[3]:
                    reconnect = match.connection.reconnect_score
                    if reconnect is not None:
                        st.caption(f"RS: {int(reconnect)}")

                st.caption(f"_{match.reason}_")

                # Expandable detail + outreach button
                detail_cols = st.columns([1, 1])
                with detail_cols[0]:
                    with st.expander("View details"):
                        render_connection_detail(match.connection_id)
                with detail_cols[1]:
                    if st.button(
                        "Generate Outreach",
                        key=f"outreach_{match.connection_id}_{i}",
                        use_container_width=True,
                    ):
                        _add_to_queue(match.connection_id)

                st.divider()

    # Navigation
    if st.button("← Back to Main"):
        st.session_state.page = "main"
        st.rerun()


def _add_to_queue(connection_id: str):
    """Generate outreach for a matched contact and add to the review queue."""
    with get_session() as session:
        connection = session.get(Connection, connection_id)
        user_profile = session.get(UserProfile, 1)
        if not connection or not user_profile:
            st.error("Could not load contact or user profile.")
            return

        channel = determine_channel(connection)
        item = generate_queue_item(connection, user_profile, channel)
        session.add(item)

    st.success(f"Added {connection.name} to the review queue!")
