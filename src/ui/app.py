"""Main Streamlit application for Reconnect."""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st

from src.database.engine import get_session, init_db
from src.database.models import Connection, UserProfile
from src.ui.components.actions import render_action_buttons, render_drafts_sidebar
from src.ui.components.detail import render_connection_detail
from src.ui.components.search import render_search_filters, search_connections

# Page config
st.set_page_config(
    page_title="Reconnect - Personal Networking CRM",
    page_icon="🤝",
    layout="wide",
)

# PWA support - inject manifest and service worker registration
st.markdown("""
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#1f77b4">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Reconnect">
<script>
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/service-worker.js')
        .then(reg => console.log('SW registered'))
        .catch(err => console.log('SW registration failed:', err));
}
</script>
""", unsafe_allow_html=True)

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


def render_sidebar_nav():
    """Render persistent sidebar navigation available on all pages."""
    with st.sidebar:
        st.header("Reconnect")

        current = st.session_state.page

        if st.button(
            "🏠 Contacts",
            use_container_width=True,
            type="primary" if current == "main" else "secondary",
        ):
            st.session_state.page = "main"
            st.rerun()

        if st.button(
            "📊 Dashboard",
            use_container_width=True,
            type="primary" if current == "dashboard" else "secondary",
        ):
            st.session_state.page = "dashboard"
            st.rerun()

        if st.button(
            "🙋 Ask My Network",
            use_container_width=True,
            type="primary" if current == "ask" else "secondary",
        ):
            st.session_state.page = "ask"
            st.rerun()

        if st.button(
            "📋 Review Queue",
            use_container_width=True,
            type="primary" if current == "review" else "secondary",
        ):
            st.session_state.page = "review"
            st.rerun()

        if st.button(
            "🔍 Find Contacts",
            use_container_width=True,
            type="primary" if current == "opportunities" else "secondary",
        ):
            st.session_state.page = "opportunities"
            st.rerun()

        if st.button(
            "🔄 Pipeline",
            use_container_width=True,
            type="primary" if current == "pipeline" else "secondary",
        ):
            st.session_state.page = "pipeline"
            st.rerun()

        if st.button(
            "⚙️ Settings",
            use_container_width=True,
            type="primary" if current == "settings" else "secondary",
        ):
            st.session_state.page = "settings"
            st.rerun()

        st.divider()


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

def render_welcome_page():
    """Render a welcome screen for first-time users with no contacts."""

    st.markdown(
        """
        <style>
        .welcome-header { text-align: center; padding: 1rem 0 0.5rem 0; }
        .welcome-sub { text-align: center; color: #666; font-size: 1.1rem; margin-bottom: 2rem; }
        .step-num { font-size: 1.5rem; font-weight: bold; color: #1f77b4; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="welcome-header">', unsafe_allow_html=True)
    st.title("Reconnect")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="welcome-sub">AI-powered networking CRM — resurface the connections that matter</p>',
        unsafe_allow_html=True,
    )

    # How it works
    st.markdown("---")
    st.subheader("How It Works")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown('<p class="step-num">1</p>', unsafe_allow_html=True)
        st.markdown("**Import**")
        st.caption(
            "Upload your LinkedIn data export. "
            "Connections, messages, endorsements — all parsed automatically."
        )

    with col2:
        st.markdown('<p class="step-num">2</p>', unsafe_allow_html=True)
        st.markdown("**Score**")
        st.caption(
            "Two-stage AI scoring ranks every contact. "
            "Rule-based pre-scoring, then LLM deep analysis on top prospects."
        )

    with col3:
        st.markdown('<p class="step-num">3</p>', unsafe_allow_html=True)
        st.markdown("**Enrich**")
        st.caption(
            "Top contacts get enriched with current roles, companies, "
            "skills, and email addresses via API."
        )

    with col4:
        st.markdown('<p class="step-num">4</p>', unsafe_allow_html=True)
        st.markdown("**Reconnect**")
        st.caption(
            "AI drafts personalized outreach. "
            "You review, edit, and send — via email or LinkedIn."
        )

    st.markdown("---")

    # Architecture at a glance
    st.subheader("Under the Hood")

    st.code(
        """
  LinkedIn Export       Two-Stage Scoring       Enrichment          Outreach
  ===============       =================       ==========          ========
  Connections.csv  -->  Stage 1: Rules     -->  RapidAPI       -->  AI-Drafted
  Messages.csv          (fast, free)            (current role)      Messages
  Endorsements          Stage 2: LLM           Hunter.io           Human Review
  Reactions             (deep analysis)         (email finder)      Gmail / LinkedIn

                  Daily Pipeline (automated, runs at 8 AM)
                  ==========================================
                  Import -> Pre-Score -> Enrich -> Score -> Queue -> Notify
        """,
        language=None,
    )

    st.markdown("---")

    # Get started
    st.subheader("Get Started")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("**Step 1: Configure your profile**")
        st.caption(
            "Tell Reconnect about your role, goals, and interests "
            "so the AI can score contacts relative to what matters to you."
        )
        if st.button("Open Settings", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()

    with col_right:
        st.markdown("**Step 2: Import your LinkedIn data**")
        st.caption(
            "Go to LinkedIn > Settings > Data Privacy > Get a copy of your data. "
            "Upload the ZIP file below."
        )
        uploaded_zip = st.file_uploader(
            "LinkedIn Data Export (ZIP)",
            type=["zip"],
            help="Full data export from LinkedIn",
            key="welcome_zip_uploader",
        )

        if uploaded_zip is not None:
            # Get user name for message direction detection
            try:
                with get_session() as session:
                    profile = session.get(UserProfile, 1)
                    user_name = profile.name if profile else None
            except Exception:
                user_name = None

            if st.button("Import", use_container_width=True, type="primary"):
                import tempfile
                from pathlib import Path

                try:
                    from src.ingestion.linkedin_dump import import_linkedin_dump

                    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                        tmp.write(uploaded_zip.getvalue())
                        tmp_path = Path(tmp.name)

                    with st.spinner("Importing LinkedIn data..."):
                        result = import_linkedin_dump(
                            tmp_path,
                            user_name=user_name,
                            summarize_conversations=False,
                        )

                        st.success(
                            f"Imported {result.connections_imported} new, "
                            f"updated {result.connections_updated}"
                        )

                    tmp_path.unlink()
                    st.rerun()

                except Exception as e:
                    st.error(f"Import failed: {str(e)}")

    st.markdown("---")

    # Tech stack
    st.caption(
        "Built with Python, Streamlit, SQLite, OpenAI, RapidAPI, Hunter.io, "
        "and Claude Code. All data stored locally by default."
    )


def render_main_page():
    """Render the main contacts page."""
    # Check if there are any contacts — show welcome screen if empty
    with get_session() as session:
        from sqlmodel import func, select

        contact_count = session.exec(select(func.count(Connection.id))).one()

    if contact_count == 0:
        render_welcome_page()
        return

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
            from src.ingestion.rapidapi_linkedin import update_connection_from_profile
            from src.llm.scoring import score_connection

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
                        if update_connection_from_profile(conn_id):
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

        # Email Finder section (Hunter.io)
        st.subheader("Find Emails")
        st.caption("Find emails for contacts missing them (Hunter.io)")

        email_batch_size = st.number_input(
            "Contacts to search",
            min_value=1,
            max_value=50,
            value=5,
            help="Number of tier-1 contacts to find emails for",
            key="email_batch_size",
        )

        # Show count of contacts missing email
        with get_session() as session:
            from sqlmodel import select

            missing_email_count = session.exec(
                select(func.count(Connection.id))
                .where(Connection.pre_score_tier == 1)
                .where((Connection.email == None) | (Connection.email == ""))
                .where(Connection.current_company != None)
            ).one()

        if missing_email_count == 0:
            st.info("All tier-1 contacts have emails!")
        else:
            st.caption(f"{missing_email_count} tier-1 contacts missing email")

            if st.button("📧 Find Emails", use_container_width=True):
                from src.ingestion.hunter import find_emails_batch, get_contacts_missing_email

                contacts = get_contacts_missing_email(limit=email_batch_size)

                if not contacts:
                    st.info("No contacts need email lookup.")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    def update_progress(current, total):
                        progress_bar.progress(current / total)
                        if current <= len(contacts):
                            status_text.text(f"Searching for {contacts[current - 1].name}...")

                    results = find_emails_batch(
                        [c.id for c in contacts],
                        progress_callback=update_progress,
                    )

                    status_text.empty()
                    progress_bar.empty()

                    st.success(
                        f"Found {results['found']} emails, "
                        f"skipped {results['skipped']}, "
                        f"failed {results['failed']}"
                    )

                    if results.get("errors"):
                        with st.expander(f"Errors ({len(results['errors'])})"):
                            for error in results["errors"][:10]:
                                st.caption(error)

                    st.rerun()

        st.divider()

        # Import section
        st.subheader("Import Data")

        # LinkedIn Data Export (ZIP) - preferred method
        uploaded_zip = st.file_uploader(
            "LinkedIn Data Export (ZIP)",
            type=["zip"],
            help="Full data export from LinkedIn: Settings > Data Privacy > Get a copy of your data",
            key="zip_uploader",
        )

        if uploaded_zip is not None:
            st.caption(f"File ready: {uploaded_zip.name} ({uploaded_zip.size} bytes)")

            # Get user name for message direction detection
            try:
                with get_session() as session:
                    profile = session.get(UserProfile, 1)
                    user_name = profile.name if profile else None
                    print(f"[DEBUG] User name: {user_name}")
            except Exception as e:
                print(f"[DEBUG] Error getting profile: {e}")
                user_name = None

            if st.button("Import ZIP", use_container_width=True, type="primary"):
                st.info("Starting import...")
                import tempfile
                import traceback
                from pathlib import Path

                print(f"[DEBUG] Starting import of {uploaded_zip.name}")

                try:
                    from src.ingestion.linkedin_dump import import_linkedin_dump

                    # Save uploaded file temporarily
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                        tmp.write(uploaded_zip.getvalue())
                        tmp_path = Path(tmp.name)

                    print(f"[DEBUG] Saved to temp file: {tmp_path}")

                    with st.spinner("Importing LinkedIn data..."):
                        result = import_linkedin_dump(
                            tmp_path,
                            user_name=user_name,
                            summarize_conversations=False,  # Skip LLM for now
                        )

                        print(f"[DEBUG] Import complete: {result}")

                        st.success(
                            f"Imported {result.connections_imported} new, "
                            f"updated {result.connections_updated}"
                        )

                        # Show additional stats
                        extras = []
                        if result.messages_processed:
                            extras.append(f"{result.messages_processed} conversations")
                        if result.engagement_signals_created:
                            extras.append(f"{result.engagement_signals_created} engagement signals")
                        if result.endorsements_processed:
                            extras.append(f"{result.endorsements_processed} endorsements")
                        if result.user_content_created:
                            extras.append(f"{result.user_content_created} posts")

                        if extras:
                            st.caption("Also processed: " + ", ".join(extras))

                        if result.errors:
                            with st.expander(f"Errors ({len(result.errors)})"):
                                for error in result.errors[:10]:
                                    st.caption(error)

                    tmp_path.unlink()  # Clean up

                except Exception as e:
                    import sys
                    print(f"[DEBUG] Import error: {e}")
                    traceback.print_exc()
                    # Also show full traceback in UI
                    st.error(f"Import failed: {str(e)}")
                    st.code(traceback.format_exc())

        # Legacy CSV import
        with st.expander("Or upload CSV only"):
            uploaded_file = st.file_uploader(
                "Connections.csv",
                type=["csv"],
                help="Just the Connections.csv file (less data than full export)",
                key="csv_uploader",
            )

            if uploaded_file is not None:
                if st.button("Import CSV", use_container_width=True):
                    import tempfile
                    from pathlib import Path

                    from src.ingestion.csv_import import import_linkedin_csv

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


def render_pipeline_page():
    """Render the pipeline management page."""
    st.title("Pipeline")
    st.caption("Run the daily pipeline to process contacts")

    from pathlib import Path
    from src.pipeline.daily_pipeline import run_daily_pipeline
    from src.pipeline.queue_generator import get_queue_stats

    # Current stats
    st.subheader("Current Status")
    stats = get_queue_stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Pending Review", stats.get("pending_review", 0))
    with col2:
        st.metric("Approved", stats.get("approved", 0))
    with col3:
        st.metric("Sent", stats.get("sent", 0))
    with col4:
        st.metric("Skipped", stats.get("skipped", 0))

    st.divider()

    # Run pipeline
    st.subheader("Run Pipeline")

    # Optional LinkedIn dump
    uploaded_file = st.file_uploader(
        "LinkedIn Data Export (optional)",
        type=["zip"],
        help="Upload your LinkedIn data export ZIP file",
    )

    col_run, col_opts = st.columns([1, 1])

    with col_opts:
        skip_enrich = st.checkbox("Skip Apify enrichment", help="Use pre-scores only")
        skip_queue = st.checkbox("Skip queue generation", help="Don't add to outreach queue")

    with col_run:
        if st.button("🚀 Run Pipeline", use_container_width=True, type="primary"):
            # Save uploaded file if provided
            dump_path = None
            if uploaded_file:
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    dump_path = Path(tmp.name)

            with st.spinner("Running pipeline..."):
                result = run_daily_pipeline(
                    linkedin_dump_path=dump_path,
                    skip_enrichment=skip_enrich,
                    skip_queue_generation=skip_queue,
                )

            # Show results
            st.success("Pipeline completed!")

            if result.get("import"):
                imp = result["import"]
                st.write(f"**Import:** {imp.get('imported', 0)} new, {imp.get('updated', 0)} updated")

            if result.get("prescore"):
                ps = result["prescore"]
                st.write(f"**Pre-scored:** {ps.get('scored', 0)} contacts")

            if result.get("enrich"):
                en = result["enrich"]
                st.write(f"**Enriched:** {en.get('success', 0)} contacts")

            if result.get("queue"):
                q = result["queue"]
                st.write(f"**Queue:** {q.get('added', 0)} added")

            # Clean up temp file
            if dump_path and dump_path.exists():
                dump_path.unlink()

def main():
    """Main application entry point."""
    # Handle URL parameters for deep linking
    query_params = st.query_params
    if "page" in query_params:
        st.session_state.page = query_params["page"]

    # Persistent sidebar navigation (available on all pages)
    render_sidebar_nav()

    # Route to appropriate page
    if st.session_state.page == "settings":
        render_settings_page()
    elif st.session_state.page == "dashboard":
        from src.ui.views.dashboard import render_dashboard_page
        render_dashboard_page()
    elif st.session_state.page == "ask":
        from src.ui.views.ask import render_ask_page
        render_ask_page()
    elif st.session_state.page == "review":
        from src.ui.views.review import render_review_page
        render_review_page()
    elif st.session_state.page == "opportunities":
        from src.ui.views.opportunities import render_opportunities_page
        render_opportunities_page()
    elif st.session_state.page == "pipeline":
        render_pipeline_page()
    else:
        render_main_page()


if __name__ == "__main__":
    main()
