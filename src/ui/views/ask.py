"""Ask My Network — find the best-fit contacts for a question."""

import streamlit as st

from src.llm.opportunity_match import find_matches
from src.ui.components.detail import render_connection_detail


def render_ask_page():
    """Render the Ask My Network page."""
    st.title("Ask My Network")
    st.caption("Ask a question and find the best-fit contacts in your network")

    question = st.text_input(
        "What do you need?",
        placeholder="e.g. Who can help me with fundraising? Who knows about machine learning?",
    )

    col_btn, col_limit = st.columns([3, 1])
    with col_limit:
        limit = st.number_input("Max results", min_value=1, max_value=50, value=10)
    with col_btn:
        st.write("")  # spacer
        search_clicked = st.button(
            "Search", use_container_width=True, type="primary"
        )

    if search_clicked and question.strip():
        with st.spinner("Searching your network..."):
            matches = find_matches(question.strip(), limit=limit)
        st.session_state.ask_matches = matches
        st.session_state.ask_question = question.strip()

    # Render results
    matches = st.session_state.get("ask_matches")

    if matches is not None and len(matches) == 0:
        st.info("No matches found. Try rephrasing your question.")
    elif matches:
        st.subheader(f"{len(matches)} matches")

        for match in matches:
            with st.container():
                cols = st.columns([0.5, 3, 1])

                with cols[0]:
                    score = match.score
                    if score >= 80:
                        st.markdown(f"**{score}**")
                    else:
                        st.markdown(f"{score}")

                with cols[1]:
                    st.markdown(f"**{match.name}**")
                    role_parts = []
                    if match.connection.current_role:
                        role_parts.append(match.connection.current_role)
                    if match.connection.current_company:
                        role_parts.append(match.connection.current_company)
                    if role_parts:
                        st.caption(" @ ".join(role_parts))

                with cols[2]:
                    if match.connection.location:
                        st.caption(match.connection.location)

                st.caption(f"_{match.reason}_")

                with st.expander("View details"):
                    render_connection_detail(match.connection_id)

                st.divider()
