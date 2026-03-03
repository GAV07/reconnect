"""Mobile-first review UI for outreach queue.

Card-based interface optimized for mobile devices and PWA installation.
Includes a compact list view for rapid batch triage.
"""

import json

import streamlit as st

from src.database.engine import get_session
from src.database.models import Connection, OutreachQueueItem, get_enrichment_data
from src.integrations.gmail import is_gmail_configured, send_email
from src.pipeline.queue_generator import (
    approve_queue_item,
    get_pending_queue,
    get_queue_stats,
    mark_item_sent,
    skip_queue_item,
)

# Shared CSS for action link buttons
_ACTION_LINK_STYLE = (
    "display:inline-block;padding:4px 10px;margin:2px;border-radius:6px;"
    "font-size:12px;text-decoration:none;font-weight:500;"
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

    # View mode toggle
    review_mode = st.radio(
        "View", ["Card", "List"], horizontal=True,
        key="review_mode", label_visibility="collapsed",
    )

    if review_mode == "Card":
        _render_card_view(pending)
    else:
        _render_batch_view(pending)


# ---------------------------------------------------------------------------
# Quick action links (HTML anchors — no page rerun)
# ---------------------------------------------------------------------------

def _render_quick_actions(connection: Connection):
    """Render clickable action links for the contact (open in new tab)."""
    links = []
    if connection.linkedin_url:
        links.append(
            f'<a href="{connection.linkedin_url}" target="_blank" '
            f'style="{_ACTION_LINK_STYLE}background:#e8f5e9;color:#2e7d32;">'
            "View Profile</a>"
        )
        dm_url = connection.linkedin_url.rstrip("/") + "/overlay/new-message/"
        links.append(
            f'<a href="{dm_url}" target="_blank" '
            f'style="{_ACTION_LINK_STYLE}background:#e3f2fd;color:#1565c0;">'
            "Send DM</a>"
        )
    if connection.email:
        from src.ui.components.actions import create_mailto_link
        mailto = create_mailto_link(connection.email)
        links.append(
            f'<a href="{mailto}" target="_blank" '
            f'style="{_ACTION_LINK_STYLE}background:#fce4ec;color:#c62828;">'
            "Email</a>"
        )
    activity = connection.activity_log or []
    if activity and activity[0].get("postUrl"):
        links.append(
            f'<a href="{activity[0]["postUrl"]}" target="_blank" '
            f'style="{_ACTION_LINK_STYLE}background:#fff3e0;color:#e65100;">'
            "See Post</a>"
        )
    if links:
        st.markdown(" ".join(links), unsafe_allow_html=True)


def _get_top_hook(connection: Connection) -> str | None:
    """Extract the first conversation hook from score_reasoning."""
    if not connection.score_reasoning:
        return None
    try:
        data = json.loads(connection.score_reasoning)
    except json.JSONDecodeError:
        return None
    hooks = data.get("conversation_hooks", [])
    return hooks[0] if hooks else None


# ---------------------------------------------------------------------------
# Card view (existing behaviour, extracted)
# ---------------------------------------------------------------------------

def _render_card_view(pending: list[tuple[OutreachQueueItem, Connection]]):
    """Render the single-card swipe-through view."""
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
            st.markdown(f"### {int(score)}")
        elif score >= 50:
            st.markdown(f"### {int(score)}")
        else:
            st.markdown(f"### {int(score)}")

    # Quick action links
    _render_quick_actions(connection)

    # Channel indicator
    channel = queue_item.channel
    if channel == "email":
        st.markdown("**Email**")
        if connection.email:
            st.caption(f"To: {connection.email}")
    else:
        st.markdown("**LinkedIn**")
        if connection.linkedin_url:
            st.caption("Will copy message to clipboard")

    # Top conversation hook (surfaced before expander)
    top_hook = _get_top_hook(connection)
    if top_hook:
        st.caption(f"Hook: {top_hook}")

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
        if st.button("Generate Draft", key=f"gen_{queue_item.id}", use_container_width=True):
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
        if st.button("Skip", use_container_width=True, type="secondary"):
            skip_queue_item(queue_item.id, reason="Skipped during review")
            _advance_to_next(len(pending))

    with col_send:
        if channel == "email":
            gmail_ready = is_gmail_configured()
            if gmail_ready:
                if st.button("Send Email", use_container_width=True, type="primary"):
                    _send_email_action(queue_item, connection, edited_message, edited_subject)
            else:
                st.button("Send Email", use_container_width=True, disabled=True)
                st.caption("Gmail not connected")
        else:
            if st.button("Copy & Open", use_container_width=True, type="primary"):
                _linkedin_action(queue_item, connection, edited_message)

    # Card navigation
    st.divider()
    nav_col1, nav_col2 = st.columns(2)

    with nav_col1:
        if st.session_state.review_index > 0:
            if st.button("Prev", use_container_width=True):
                st.session_state.review_index -= 1
                st.rerun()

    with nav_col2:
        if st.session_state.review_index < len(pending) - 1:
            if st.button("Next", use_container_width=True):
                st.session_state.review_index += 1
                st.rerun()


# ---------------------------------------------------------------------------
# List / batch view
# ---------------------------------------------------------------------------

def _render_batch_view(pending: list[tuple[OutreachQueueItem, Connection]]):
    """Render a compact list of all pending contacts for rapid triage."""
    st.caption(f"{len(pending)} contacts pending review")

    for i, (item, conn) in enumerate(pending):
        col_name, col_score, col_hook, col_actions = st.columns([3, 1, 3, 2])

        with col_name:
            st.markdown(f"**{conn.name}**")
            role_parts = []
            if conn.current_role:
                role_parts.append(conn.current_role)
            if conn.current_company:
                role_parts.append(f"@ {conn.current_company}")
            if role_parts:
                st.caption(" ".join(role_parts))

        with col_score:
            score = conn.reconnect_score or conn.pre_score or 0
            st.markdown(f"**{int(score)}**")
            st.caption(item.channel or "")

        with col_hook:
            top_hook = _get_top_hook(conn)
            if top_hook:
                st.caption(top_hook[:80] + ("..." if len(top_hook) > 80 else ""))
            _render_quick_actions(conn)

        with col_actions:
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("Skip", key=f"list_skip_{item.id}", use_container_width=True):
                    skip_queue_item(item.id, reason="Skipped in list view")
                    st.rerun()
            with btn_col2:
                if st.button("View", key=f"list_view_{item.id}", use_container_width=True):
                    st.session_state.review_index = i
                    st.session_state.review_mode = "Card"
                    st.rerun()

        # Light separator between rows
        if i < len(pending) - 1:
            st.markdown("<hr style='margin:4px 0;border:none;border-top:1px solid #eee;'>",
                        unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Shared helpers (profile context, dimension bars, navigation, send actions)
# ---------------------------------------------------------------------------

def _render_profile_context(connection: Connection):
    """Render the 'About this person' expandable section on review cards."""
    enrichment = get_enrichment_data(connection)
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
                st.caption(f"Location: {location}")

        # --- Recent activity ---
        activity_log = connection.activity_log or []
        if activity_log:
            st.markdown("**Recent activity**")
            post = activity_log[0]
            content = post.get("content", "")[:200]
            if content:
                st.caption(f'"{content}"')

        # --- Career context ---
        experiences = (
            enrichment.get("experiences")
            or enrichment.get("experience")
            or []
        )
        total_years = enrichment.get("totalExperienceYears") or enrichment.get("total_experience_years")
        if experiences:
            st.markdown("**Career**")
            current = experiences[0]
            current_title = current.get("title", "")
            current_company = current.get("company") or current.get("companyName") or ""
            if current_title or current_company:
                label = f"**{current_title}**" if current_title else ""
                if current_company:
                    label += f" at {current_company}" if label else current_company
                st.markdown(label)

            for exp in experiences[1:3]:
                title = exp.get("title", "")
                company = exp.get("company") or exp.get("companyName") or ""
                if title or company:
                    parts = [p for p in [title, company] if p]
                    st.caption(f"Previously: {' at '.join(parts)}")

            if total_years:
                st.caption(f"{total_years} years experience")

        # --- Quick stats ---
        connections_count = enrichment.get("connection_count") or enrichment.get("connectionsCount")
        is_creator = enrichment.get("is_creator") or enrichment.get("isCreator", False)
        follower_count = enrichment.get("follower_count") or enrichment.get("followerCount")
        badges = []
        if is_creator:
            badges.append("Creator")
        if follower_count and isinstance(follower_count, (int, float)) and follower_count > 1000:
            badges.append(f"{int(follower_count):,} followers")
        if connections_count and isinstance(connections_count, (int, float)):
            badges.append(f"{int(connections_count):,}+ connections")
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
    if st.button("Mark as Sent", use_container_width=True):
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
