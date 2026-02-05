"""Connection detail view component for Reconnect UI."""

import json

import streamlit as st

from src.database.engine import get_session
from src.database.models import Connection


def format_activity_item(activity: dict) -> str:
    """Format a single activity item for display."""
    content = activity.get("content", "")
    url = activity.get("url", "")

    # Truncate long content
    display_content = content[:200] + "..." if len(content) > 200 else content

    if url:
        return f"📝 {display_content} [→]({url})"
    return f"📝 {display_content}"


def render_connection_detail(connection_id: str):
    """Render the detail view for a connection."""
    with get_session() as session:
        connection = session.get(Connection, connection_id)
        if not connection:
            st.error("Connection not found")
            return

        enrichment = connection.raw_enrichment or {}

        # Header with profile pic if available
        col_pic, col_info = st.columns([1, 4])

        with col_pic:
            if enrichment.get("profilePic"):
                st.image(enrichment.get("profilePic"), width=80)

        with col_info:
            st.subheader(connection.name)
            if enrichment.get("headline"):
                st.caption(enrichment.get("headline"))
            elif connection.current_role:
                st.caption(f"{connection.current_role} at {connection.current_company or ''}")

        # AI Score section (if scored)
        if connection.reconnect_score is not None:
            score = int(connection.reconnect_score)
            if score >= 70:
                score_color = "🔥"
                score_label = "High Priority"
            elif score >= 50:
                score_color = "👍"
                score_label = "Worth Reaching Out"
            else:
                score_color = "➖"
                score_label = "Lower Priority"

            st.markdown(f"### {score_color} Reconnect Score: **{score}**/100")
            st.caption(score_label)

            # Show reasoning if available
            if connection.score_reasoning:
                try:
                    reasoning = json.loads(connection.score_reasoning)
                    st.markdown(f"_{reasoning.get('reasoning', '')}_")

                    # Show conversation hooks
                    hooks = reasoning.get("conversation_hooks", [])
                    if hooks:
                        st.markdown("**Conversation starters:**")
                        for hook in hooks[:3]:
                            st.markdown(f"• {hook}")
                except json.JSONDecodeError:
                    pass

            st.divider()

        # Stats row
        if enrichment:
            stat_cols = st.columns(4)
            with stat_cols[0]:
                if enrichment.get("connections"):
                    st.metric("Connections", f"{enrichment.get('connections'):,}")
            with stat_cols[1]:
                if enrichment.get("followers"):
                    st.metric("Followers", f"{enrichment.get('followers'):,}")
            with stat_cols[2]:
                if enrichment.get("totalExperienceYears"):
                    st.metric("Experience", f"{enrichment.get('totalExperienceYears'):.0f} yrs")
            with stat_cols[3]:
                badges = []
                if enrichment.get("isCreator"):
                    badges.append("Creator")
                if enrichment.get("isPremium"):
                    badges.append("Premium")
                if enrichment.get("isInfluencer"):
                    badges.append("Influencer")
                if badges:
                    st.metric("Status", ", ".join(badges))

        # Location and contact
        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            if connection.location:
                st.write(f"📍 {connection.location}")
            if connection.email:
                st.write(f"📧 {connection.email}")

        with col2:
            if connection.linkedin_url:
                st.markdown(f"[🔗 LinkedIn Profile]({connection.linkedin_url})")
            if enrichment.get("companyWebsite"):
                st.markdown(f"[🌐 Company Website]({enrichment.get('companyWebsite')})")

        # About section
        if enrichment.get("about"):
            st.divider()
            st.write("**About**")
            about_text = enrichment.get("about")
            if len(about_text) > 500:
                with st.expander("Show full bio"):
                    st.write(about_text)
            else:
                st.write(about_text)

        # Recent posts
        st.divider()
        st.write("**Recent Posts**")

        activity_log = connection.activity_log or []

        if activity_log:
            for i, activity in enumerate(activity_log[:5]):
                content = activity.get("content", "")
                url = activity.get("url", "")

                with st.container():
                    # Truncate for display
                    display = content[:300] + "..." if len(content) > 300 else content
                    st.markdown(f"_{display}_")
                    if url:
                        st.caption(f"[View post]({url})")
                    if i < len(activity_log[:5]) - 1:
                        st.markdown("---")
        else:
            st.caption("No posts recorded yet. Click 'Enrich Profile' to fetch recent activity.")

        # Experience timeline
        experiences = enrichment.get("experiences", [])
        if experiences:
            st.divider()
            st.write("**Experience**")

            for exp in experiences[:4]:  # Show last 4 roles
                title = exp.get("title", "Unknown Role")
                company = exp.get("companyName", "Unknown Company")
                started = exp.get("jobStartedOn", "")
                ended = exp.get("jobEndedOn", "Present") or "Present"
                still_working = exp.get("jobStillWorking", False)

                date_range = f"{started} - {'Present' if still_working else ended}"

                st.markdown(f"**{title}** at {company}")
                st.caption(date_range)

                if exp.get("jobDescription"):
                    desc = exp.get("jobDescription")
                    if len(desc) > 150:
                        st.caption(desc[:150] + "...")
                    else:
                        st.caption(desc)

        # Skills
        skills = enrichment.get("skills", [])
        if skills:
            st.divider()
            st.write("**Skills**")
            skill_names = [s.get("title", s) if isinstance(s, dict) else s for s in skills[:12]]
            st.write(" • ".join(skill_names))

        # Education
        educations = enrichment.get("educations", [])
        if educations:
            st.divider()
            st.write("**Education**")
            for edu in educations[:3]:
                school = edu.get("schoolName", "")
                degree = edu.get("degree", "")
                field = edu.get("fieldOfStudy", "")
                if school:
                    edu_line = f"**{school}**"
                    if degree or field:
                        edu_line += f" - {degree} {field}".strip()
                    st.markdown(edu_line)

        # Notes (user-added)
        if connection.notes:
            st.divider()
            st.write("**Your Notes**")
            st.info(connection.notes)

        # Tags
        if connection.tags:
            st.divider()
            tags = connection.tags.split(",")
            st.write("**Tags:** " + " ".join([f"`{t.strip()}`" for t in tags]))

        # Enrichment timestamp
        if connection.enriched_at:
            st.divider()
            st.caption(f"Last enriched: {connection.enriched_at.strftime('%Y-%m-%d %H:%M')}")

        return connection
