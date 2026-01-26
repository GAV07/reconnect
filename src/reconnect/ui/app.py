"""Main Streamlit application for Reconnect."""

import streamlit as st

from reconnect.database.engine import get_session, init_db
from reconnect.database.models import Connection, UserProfile
from reconnect.ui.components.actions import render_action_buttons, render_drafts_sidebar
from reconnect.ui.components.detail import render_connection_detail
from reconnect.ui.components.search import render_search_filters, search_connections

# Page config
st.set_page_config(
    page_title="Reconnect - Personal Networking CRM",
    page_icon="🤝",
    layout="wide",
)

# Initialize database
init_db()

# Initialize session state
if "selected_connection_id" not in st.session_state:
    st.session_state.selected_connection_id = None
if "page" not in st.session_state:
    st.session_state.page = "main"
if "outreach_drafts" not in st.session_state:
    st.session_state.outreach_drafts = {}
if "show_detail_dialog" not in st.session_state:
    st.session_state.show_detail_dialog = False


def render_settings_page():
    """Render the user profile settings page."""
    st.title("Settings")
    st.caption("Configure your profile for personalized outreach suggestions")

    with get_session() as session:
        user_profile = session.get(UserProfile, 1)

        # Create default profile if not exists
        if not user_profile:
            user_profile = UserProfile(id=1, name="")

        with st.form("user_profile_form"):
            st.subheader("Your Profile")

            name = st.text_input("Your Name", value=user_profile.name or "")
            current_role = st.text_input("Current Role", value=user_profile.current_role or "")
            company = st.text_input("Company", value=user_profile.company or "")
            industry = st.text_input("Industry", value=user_profile.industry or "")

            st.subheader("Context for AI Suggestions")

            goals = st.text_area(
                "Your Networking Goals",
                value=user_profile.goals or "",
                help="What are you looking to achieve? (e.g., Find co-founders, explore new roles, build industry connections)",
                height=100,
            )

            interests = st.text_area(
                "Your Interests & Topics",
                value=user_profile.interests or "",
                help="Topics you're interested in discussing (e.g., AI/ML, startup growth, product management)",
                height=100,
            )

            submitted = st.form_submit_button("Save Profile", use_container_width=True)

            if submitted:
                user_profile.name = name
                user_profile.current_role = current_role
                user_profile.company = company
                user_profile.industry = industry
                user_profile.goals = goals
                user_profile.interests = interests

                session.add(user_profile)
                session.commit()

                st.success("Profile saved!")

    if st.button("← Back to Contacts"):
        st.session_state.page = "main"
        st.rerun()


def render_main_page():
    """Render the main contacts page."""
    st.title("Reconnect")
    st.caption("Your personal networking CRM")

    # Sidebar for filters
    with st.sidebar:
        st.header("Search & Filter")
        filters = render_search_filters()

        st.divider()

        # Quick stats
        with get_session() as session:
            from sqlmodel import func, select

            total = session.exec(select(func.count(Connection.id))).one()
            enriched = session.exec(
                select(func.count(Connection.id)).where(Connection.enriched_at.isnot(None))
            ).one()
            scored = session.exec(
                select(func.count(Connection.id)).where(Connection.reconnect_score.isnot(None))
            ).one()

        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.metric("Total", total)
        with col_stat2:
            st.metric("Enriched", enriched)
        with col_stat3:
            st.metric("Scored", scored)

        st.divider()

        # Combined Enrich + Score section
        st.subheader("Enrich & Score")
        batch_size = st.number_input(
            "Contacts to process",
            min_value=1,
            max_value=20,
            value=5,
            help="Number of contacts to enrich and score",
        )

        # Check if user profile is configured for scoring
        with get_session() as session:
            user_profile = session.get(UserProfile, 1)
            has_goals = user_profile and user_profile.goals

        if not has_goals:
            st.warning("Set your goals in Settings to enable scoring!")

        if st.button("🚀 Enrich & Score Next Batch", use_container_width=True):
            from reconnect.ingestion.apify_client import update_connection_activity
            from reconnect.llm.scoring import score_connection

            # Get un-enriched contacts
            with get_session() as session:
                un_enriched = session.exec(
                    select(Connection)
                    .where(Connection.enriched_at.is_(None))
                    .where(Connection.linkedin_url.isnot(None))
                    .limit(batch_size)
                ).all()
                contacts_to_process = [(conn.id, conn.name) for conn in un_enriched]

            if not contacts_to_process:
                st.info("All contacts with LinkedIn URLs have been enriched!")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()

                enrich_success = 0
                enrich_fail = 0
                score_success = 0
                score_fail = 0

                total_steps = len(contacts_to_process) * 2  # enrich + score

                for i, (conn_id, conn_name) in enumerate(contacts_to_process):
                    # Step 1: Enrich
                    status_text.text(f"Enriching {conn_name}...")
                    enriched = False
                    try:
                        if update_connection_activity(conn_id):
                            enrich_success += 1
                            enriched = True
                        else:
                            enrich_fail += 1
                    except Exception as e:
                        enrich_fail += 1
                        st.caption(f"Enrich error: {conn_name}: {str(e)[:40]}")

                    progress_bar.progress((i * 2 + 1) / total_steps)

                    # Step 2: Score (only if enriched and user has goals)
                    if enriched and has_goals:
                        status_text.text(f"Scoring {conn_name}...")
                        try:
                            result = score_connection(conn_id)
                            if result:
                                score_success += 1
                            else:
                                score_fail += 1
                        except Exception as e:
                            score_fail += 1
                            st.caption(f"Score error: {conn_name}: {str(e)[:40]}")

                    progress_bar.progress((i * 2 + 2) / total_steps)

                status_text.empty()
                progress_bar.empty()

                # Summary message
                msg = f"Enriched {enrich_success}/{len(contacts_to_process)}"
                if has_goals:
                    msg += f", Scored {score_success}/{enrich_success}"
                st.success(msg)
                st.rerun()

        st.divider()

        # Navigation
        if st.button("⚙️ Settings", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()

        st.divider()

        # Import section
        st.subheader("Import Contacts")
        uploaded_file = st.file_uploader(
            "Upload LinkedIn CSV",
            type=["csv"],
            help="Export your connections from LinkedIn Settings > Data Privacy > Get a copy of your data",
        )

        if uploaded_file is not None:
            if st.button("Import CSV", use_container_width=True):
                import tempfile
                from pathlib import Path

                from reconnect.ingestion.csv_import import import_linkedin_csv

                # Save uploaded file temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = Path(tmp.name)

                with st.spinner("Importing contacts..."):
                    result = import_linkedin_csv(tmp_path)

                tmp_path.unlink()  # Clean up

                st.success(f"Imported {result.imported} new, updated {result.updated}")
                if result.errors:
                    with st.expander(f"Errors ({len(result.errors)})"):
                        for error in result.errors[:10]:
                            st.caption(error)

                st.rerun()

        # Drafts section
        render_drafts_sidebar()

    # Main content area - full width contact list
    st.subheader("Contacts")

    # Search results
    connections = search_connections(filters)

    if not connections:
        st.info(
            "No contacts found. Try adjusting your filters or import contacts from LinkedIn."
        )
    else:
        # Create a more spacious table-like layout
        for conn in connections:
            with st.container():
                cols = st.columns([0.5, 2.5, 2, 1.5, 0.8])

                with cols[0]:
                    # Score display (or enrichment status if not scored)
                    if conn.reconnect_score is not None:
                        score = int(conn.reconnect_score)
                        if score >= 70:
                            st.markdown(f"🔥 **{score}**")
                        elif score >= 50:
                            st.markdown(f"👍 {score}")
                        else:
                            st.markdown(f"➖ {score}")
                    elif conn.enriched_at:
                        st.write("✅")
                    else:
                        st.write("⬜")

                with cols[1]:
                    st.write(f"**{conn.name}**")

                with cols[2]:
                    if conn.current_role:
                        st.caption(conn.current_role)

                with cols[3]:
                    if conn.current_company:
                        st.caption(conn.current_company)

                with cols[4]:
                    if st.button(
                        "View",
                        key=f"view_{conn.id}",
                        use_container_width=True,
                    ):
                        st.session_state.selected_connection_id = conn.id
                        st.session_state.show_detail_dialog = True
                        st.rerun()

                st.divider()

    # Show detail dialog if a connection is selected
    if st.session_state.get("show_detail_dialog") and st.session_state.selected_connection_id:
        show_connection_dialog(st.session_state.selected_connection_id)


@st.dialog("Contact Details", width="large")
def show_connection_dialog(connection_id: str):
    """Show connection details in a modal dialog."""
    # Action buttons at the top (full width)
    render_action_buttons(connection_id)

    st.divider()

    # Full-width detail content below
    render_connection_detail(connection_id)


def main():
    """Main application entry point."""
    if st.session_state.page == "settings":
        render_settings_page()
    else:
        render_main_page()


if __name__ == "__main__":
    main()
