"""Mobile-first review UI for outreach queue.

Card-based interface optimized for mobile devices and PWA installation.
"""

import json

import streamlit as st

from src.database.engine import get_session
from src.database.models import Connection, OutreachQueueItem
from src.integrations.gmail import is_gmail_configured, send_email
from src.pipeline.queue_generator import (
    approve_queue_item,
    get_pending_queue,
    get_queue_stats,
    mark_item_sent,
    skip_queue_item,
)


def render_review_page():
    """Render the mobile-first review page."""
    st.title("Review Queue")

    # Queue stats
    stats = get_queue_stats()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Pending", stats.get("pending_review", 0))
    with col2:
        st.metric("Approved", stats.get("approved", 0))
    with col3:
        st.metric("Sent", stats.get("sent", 0))

    st.divider()

    # Get pending items
    pending = get_pending_queue()

    if not pending:
        st.info("No contacts in queue. Run the pipeline to generate new suggestions.")
        return

    # Initialize current card index
    if "review_index" not in st.session_state:
        st.session_state.review_index = 0

    # Ensure index is valid
    if st.session_state.review_index >= len(pending):
        st.session_state.review_index = 0

    # Get current item
    queue_item, connection = pending[st.session_state.review_index]

    # Progress indicator
    st.caption(f"Contact {st.session_state.review_index + 1} of {len(pending)}")

    # Card container with mobile-optimized styling
    st.markdown("""
    <style>
    .review-card {
        border: 1px solid #ddd;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 16px;
        background: white;
    }
    .score-badge {
        font-size: 24px;
        font-weight: bold;
        color: #1f77b4;
    }
    .contact-name {
        font-size: 20px;
        font-weight: bold;
        margin-bottom: 4px;
    }
    .contact-role {
        color: #666;
        font-size: 14px;
    }
    .channel-badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        margin-top: 8px;
    }
    .channel-email {
        background: #e3f2fd;
        color: #1565c0;
    }
    .channel-linkedin {
        background: #e8f5e9;
        color: #2e7d32;
    }
    </style>
    """, unsafe_allow_html=True)

    # Card header
    col_info, col_score = st.columns([3, 1])
    with col_info:
        st.markdown(f"### {connection.name}")
        if connection.current_role:
            st.caption(f"{connection.current_role}")
        if connection.current_company:
            st.caption(f"at {connection.current_company}")

    with col_score:
        score = connection.reconnect_score or connection.pre_score or 0
        if score >= 70:
            st.markdown(f"### 🔥 {int(score)}")
        elif score >= 50:
            st.markdown(f"### 👍 {int(score)}")
        else:
            st.markdown(f"### {int(score)}")

    # Channel indicator
    channel = queue_item.channel
    if channel == "email":
        st.markdown("📧 **Email**")
        if connection.email:
            st.caption(f"To: {connection.email}")
    else:
        st.markdown("💼 **LinkedIn**")
        if connection.linkedin_url:
            st.caption("Will copy message to clipboard")

    st.divider()

    # Profile context section
    _render_profile_context(connection)

    st.divider()

    # Editable message
    st.markdown("**Draft Message:**")

    # Use session state to track edits
    edit_key = f"edit_{queue_item.id}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = queue_item.draft_message or ""

    # Generate Draft button when no draft exists
    if not queue_item.draft_message and not st.session_state[edit_key]:
        if st.button("✨ Generate Draft", key=f"gen_{queue_item.id}", use_container_width=True):
            with st.spinner("Generating draft..."):
                from src.llm.prose import generate_outreach_message
                from src.database.engine import get_session as _get_session
                from src.database.models import UserProfile as _UP

                with _get_session() as _sess:
                    _profile = _sess.get(_UP, 1)
                    if not _profile:
                        _profile = _UP(id=1, name="")
                    draft = generate_outreach_message(connection, _profile, channel=channel)

                # Save to DB
                with _get_session() as _sess:
                    _item = _sess.get(type(queue_item), queue_item.id)
                    if _item:
                        _item.draft_message = draft
                        _sess.add(_item)

                st.session_state[edit_key] = draft
                st.rerun()

    edited_message = st.text_area(
        "Message",
        value=st.session_state[edit_key],
        height=200,
        key=f"textarea_{queue_item.id}",
        label_visibility="collapsed",
    )

    # Update session state if edited
    st.session_state[edit_key] = edited_message

    # Subject line for email
    edited_subject = None
    if channel == "email":
        subject_key = f"subject_{queue_item.id}"
        if subject_key not in st.session_state:
            st.session_state[subject_key] = queue_item.draft_subject or "Reconnecting"

        edited_subject = st.text_input(
            "Subject",
            value=st.session_state[subject_key],
            key=f"subject_input_{queue_item.id}",
        )
        st.session_state[subject_key] = edited_subject

    st.divider()

    # Action buttons
    col_skip, col_send = st.columns(2)

    with col_skip:
        if st.button("⏭️ Skip", use_container_width=True, type="secondary"):
            skip_queue_item(queue_item.id, reason="Skipped during review")
            _advance_to_next(len(pending))

    with col_send:
        if channel == "email":
            gmail_ready = is_gmail_configured()
            if gmail_ready:
                if st.button("📤 Send Email", use_container_width=True, type="primary"):
                    _send_email_action(queue_item, connection, edited_message, edited_subject)
            else:
                st.button("📤 Send Email", use_container_width=True, disabled=True)
                st.caption("Gmail not connected")
        else:
            if st.button("📋 Copy & Open", use_container_width=True, type="primary"):
                _linkedin_action(queue_item, connection, edited_message)

    # Card navigation
    st.divider()
    nav_col1, nav_col2 = st.columns(2)

    with nav_col1:
        if st.session_state.review_index > 0:
            if st.button("← Prev", use_container_width=True):
                st.session_state.review_index -= 1
                st.rerun()

    with nav_col2:
        if st.session_state.review_index < len(pending) - 1:
            if st.button("Next →", use_container_width=True):
                st.session_state.review_index += 1
                st.rerun()


def _render_profile_context(connection: Connection):
    """Render the 'About this person' expandable section on review cards."""
    enrichment = connection.raw_enrichment or {}
    reasoning_data = {}
    if connection.score_reasoning:
        try:
            reasoning_data = json.loads(connection.score_reasoning)
        except json.JSONDecodeError:
            pass

    with st.expander("About this person", expanded=False):
        # --- Why reach out ---
        key_factors = reasoning_data.get("key_factors", [])
        hooks = reasoning_data.get("conversation_hooks", [])
        if key_factors or hooks:
            st.markdown("**Why reach out**")
            if reasoning_data.get("reasoning"):
                st.caption(reasoning_data["reasoning"])
            if hooks:
                for hook in hooks:
                    st.markdown(f"- {hook}")

        # --- Score breakdown (dimension bars) ---
        dimension_scores = reasoning_data.get("dimension_scores", {})
        if dimension_scores:
            st.markdown("**Score breakdown**")
            _render_dimension_bars(dimension_scores)

        # --- Profile snapshot ---
        headline = enrichment.get("headline", "")
        about = enrichment.get("about", "") or enrichment.get("summary", "")
        location = (
            connection.location
            or enrichment.get("addressWithCountry", "")
        )
        if headline or about or location:
            st.markdown("**Profile**")
            if headline:
                st.markdown(f"*{headline}*")
            if about:
                # Truncate to ~200 chars
                truncated = about[:200] + ("..." if len(about) > 200 else "")
                st.caption(truncated)
            if location:
                st.caption(f"📍 {location}")

        # --- Recent activity ---
        activity_log = connection.activity_log or []
        if activity_log:
            st.markdown("**Recent activity**")
            post = activity_log[0]
            content = post.get("content", "")[:200]
            if content:
                st.caption(f'"{content}"')

        # --- Career context ---
        experiences = enrichment.get("experiences", [])
        total_years = enrichment.get("totalExperienceYears")
        if experiences:
            st.markdown("**Career**")
            # Current role
            current = experiences[0] if experiences else {}
            current_title = current.get("title", "")
            current_company = current.get("companyName", "")
            if current_title and current_company:
                st.markdown(f"**{current_title}** at {current_company}")

            # Previous roles (1-2)
            for exp in experiences[1:3]:
                title = exp.get("title", "")
                company = exp.get("companyName", "")
                if title and company:
                    st.caption(f"Previously: {title} at {company}")

            if total_years:
                st.caption(f"{total_years} years experience")

        # --- Quick stats ---
        connections_count = enrichment.get("connectionsCount")
        is_creator = enrichment.get("isCreator", False)
        follower_count = enrichment.get("followerCount")
        badges = []
        if is_creator:
            badges.append("Creator")
        if follower_count and follower_count > 1000:
            badges.append(f"{follower_count:,} followers")
        if connections_count:
            badges.append(f"{connections_count:,}+ connections")
        if badges:
            st.markdown("**Stats:** " + " · ".join(badges))


def _render_dimension_bars(dimension_scores: dict):
    """Render dimension scores as labeled progress bars."""
    dimensions = {
        "goal_alignment": ("Goal Alignment", 25),
        "industry_overlap": ("Industry Overlap", 20),
        "mutual_value": ("Mutual Value", 20),
        "conversation_hooks": ("Hooks", 20),
        "network_reach": ("Network Reach", 15),
    }
    for key, (label, max_pts) in dimensions.items():
        pts = dimension_scores.get(key, 0)
        pct = pts / max_pts if max_pts > 0 else 0
        st.caption(f"{label}: {pts}/{max_pts}")
        st.progress(min(pct, 1.0))


def _advance_to_next(total: int):
    """Advance to next card or wrap around."""
    if st.session_state.review_index < total - 1:
        st.session_state.review_index += 1
    else:
        st.session_state.review_index = 0
    st.rerun()


def _send_email_action(
    queue_item: OutreachQueueItem,
    connection: Connection,
    message: str,
    subject: str,
):
    """Send email and update queue item."""
    if not connection.email:
        st.error("No email address for this contact")
        return

    try:
        # Save any edits first
        approve_queue_item(queue_item.id, edited_message=message)

        # Send email
        result = send_email(
            to=connection.email,
            subject=subject or "Reconnecting",
            body=message,
        )

        # Mark as sent
        mark_item_sent(queue_item.id)

        st.success(f"Email sent to {connection.email}!")

        # Get new count and advance
        pending = get_pending_queue()
        _advance_to_next(len(pending))

    except Exception as e:
        st.error(f"Failed to send: {str(e)}")


def _linkedin_action(
    queue_item: OutreachQueueItem,
    connection: Connection,
    message: str,
):
    """Copy message and open LinkedIn."""
    # Save edits and approve
    approve_queue_item(queue_item.id, edited_message=message)

    # Copy to clipboard using JavaScript
    st.markdown(f"""
    <script>
    navigator.clipboard.writeText(`{message.replace('`', '\\`')}`);
    </script>
    """, unsafe_allow_html=True)

    # Also show the message for manual copy (JS may be blocked)
    st.code(message, language=None)
    st.caption("Message copied! (If not, copy above)")

    # Open LinkedIn in new tab
    if connection.linkedin_url:
        st.markdown(f"""
        <a href="{connection.linkedin_url}" target="_blank">
            <button style="
                background-color: #0077B5;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                width: 100%;
            ">
                Open LinkedIn Profile
            </button>
        </a>
        """, unsafe_allow_html=True)

    # Mark as sent when user confirms
    if st.button("✅ Mark as Sent", use_container_width=True):
        mark_item_sent(queue_item.id)
        pending = get_pending_queue()
        _advance_to_next(len(pending))


def render_gmail_settings():
    """Render Gmail connection settings."""
    st.subheader("Gmail Integration")

    if is_gmail_configured():
        from src.integrations.gmail import get_user_email, disconnect_gmail

        email = get_user_email()
        st.success(f"Connected as: {email or 'Unknown'}")

        if st.button("Disconnect Gmail"):
            disconnect_gmail()
            st.rerun()
    else:
        st.warning("Gmail not connected. Connect to send emails directly.")

        if settings_gmail_client_configured():
            from src.integrations.gmail import get_gmail_auth_url

            auth_url = get_gmail_auth_url()
            st.markdown(f"[Connect Gmail]({auth_url})")
            st.caption("You'll be redirected to Google to authorize.")
        else:
            st.info("Gmail OAuth not configured. Add GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET to .env")


def settings_gmail_client_configured() -> bool:
    """Check if Gmail OAuth client is configured in settings."""
    from src.config import settings
    return bool(settings.gmail_client_id and settings.gmail_client_secret)
