"""Connection detail view component for Reconnect UI."""

import json

import streamlit as st

from src.database.engine import get_session
from src.database.models import Connection, get_enrichment_data


# ---------------------------------------------------------------------------
# Helpers — extract fields from RapidAPI's exact response format
# ---------------------------------------------------------------------------

def _get_experiences(enrichment: dict) -> list[dict]:
    return enrichment.get("experiences") or enrichment.get("experience") or []


def _get_educations(enrichment: dict) -> list[dict]:
    return enrichment.get("educations") or enrichment.get("education") or []


def _get_skills(enrichment: dict) -> list[str]:
    """Collect skills from top-level array OR from experience skill strings."""
    # Try top-level skills array first
    raw = enrichment.get("skills")
    if isinstance(raw, list) and raw:
        result = []
        for s in raw[:15]:
            if isinstance(s, dict):
                result.append(s.get("title") or s.get("name") or "")
            elif isinstance(s, str):
                result.append(s)
        return [s for s in result if s]

    # Aggregate from experience entries (RapidAPI format: " · " separated strings)
    seen = set()
    skills = []
    for exp in _get_experiences(enrichment):
        exp_skills = exp.get("skills", "")
        if isinstance(exp_skills, str) and exp_skills:
            for s in exp_skills.split(" · "):
                s = s.strip()
                if s and s not in seen:
                    seen.add(s)
                    skills.append(s)
    return skills[:15]


def _exp_company(exp: dict) -> str:
    return exp.get("company") or exp.get("companyName") or exp.get("company_name") or ""


def _exp_date_range(exp: dict) -> str:
    """Use the pre-formatted date_range if available, otherwise build one."""
    if exp.get("date_range"):
        return exp["date_range"]
    start_y = exp.get("start_year", "")
    start_m = exp.get("start_month", "")
    if exp.get("is_current"):
        end = "Present"
    else:
        end_y = exp.get("end_year", "")
        end_m = exp.get("end_month", "")
        end = f"{end_m}/{end_y}" if end_m and end_y else str(end_y) if end_y else "Present"
    start = f"{start_m}/{start_y}" if start_m and start_y else str(start_y) if start_y else ""
    return f"{start} - {end}" if start else end


def _get_count(enrichment: dict, *keys) -> int | None:
    for k in keys:
        v = enrichment.get(k)
        if v is not None and v != "":
            try:
                return int(v)
            except (TypeError, ValueError):
                pass
    return None


def _get_profile_pic(enrichment: dict) -> str | None:
    for key in ("profile_image_url", "profilePic", "profile_pic_url"):
        if enrichment.get(key):
            return enrichment[key]
    avatar = enrichment.get("avatar")
    if isinstance(avatar, list) and avatar and isinstance(avatar[0], dict):
        return avatar[0].get("url")
    return None


# ---------------------------------------------------------------------------
# Main detail renderer
# ---------------------------------------------------------------------------

def render_connection_detail(connection_id: str):
    """Render the detail view for a connection."""
    with get_session() as session:
        connection = session.get(Connection, connection_id)
        if not connection:
            st.error("Connection not found")
            return

        enrichment = get_enrichment_data(connection)

        # Header with profile pic
        pic_url = _get_profile_pic(enrichment)
        col_pic, col_info = st.columns([1, 4])

        with col_pic:
            if pic_url:
                st.image(pic_url, width=80)

        with col_info:
            st.subheader(connection.name)
            if enrichment.get("headline"):
                st.caption(enrichment["headline"])
            elif connection.current_role:
                st.caption(f"{connection.current_role} at {connection.current_company or ''}")

        # AI Score section
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

            if connection.score_reasoning:
                try:
                    reasoning = json.loads(connection.score_reasoning)
                    st.markdown(f"_{reasoning.get('reasoning', '')}_")

                    hooks = reasoning.get("conversation_hooks", [])
                    if hooks:
                        st.markdown("**Conversation starters:**")
                        for hook in hooks[:3]:
                            st.markdown(f"- {hook}")
                except json.JSONDecodeError:
                    pass

            st.divider()

        # Stats row
        connections_count = _get_count(enrichment, "connection_count", "connectionsCount", "connections_count", "connections")
        followers_count = _get_count(enrichment, "follower_count", "followerCount", "followers_count", "followers")

        is_creator = enrichment.get("is_creator") or enrichment.get("isCreator", False)
        is_premium = enrichment.get("is_premium") or enrichment.get("isPremium", False)
        is_influencer = enrichment.get("is_influencer") or enrichment.get("isInfluencer", False)

        has_stats = connections_count or followers_count or is_creator or is_premium or is_influencer
        if has_stats:
            stat_cols = st.columns(4)
            with stat_cols[0]:
                if connections_count:
                    st.metric("Connections", f"{connections_count:,}")
            with stat_cols[1]:
                if followers_count:
                    st.metric("Followers", f"{followers_count:,}")
            with stat_cols[2]:
                duration = enrichment.get("current_job_duration")
                if duration:
                    st.metric("Current Role", duration)
            with stat_cols[3]:
                badges = []
                if is_creator:
                    badges.append("Creator")
                if is_premium:
                    badges.append("Premium")
                if is_influencer:
                    badges.append("Influencer")
                if badges:
                    st.metric("Status", ", ".join(badges))

        # Location and contact
        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            location = connection.location or enrichment.get("location", "")
            if location:
                st.write(f"📍 {location}")
            if connection.email:
                st.write(f"📧 {connection.email}")

        with col2:
            if connection.linkedin_url:
                st.markdown(f"[🔗 LinkedIn Profile]({connection.linkedin_url})")
            company_website = enrichment.get("company_website") or enrichment.get("companyWebsite")
            if company_website:
                st.markdown(f"[🌐 Company Website]({company_website})")

        # About section
        about = enrichment.get("about") or enrichment.get("summary") or ""
        if about:
            st.divider()
            st.write("**About**")
            if len(about) > 500:
                with st.expander("Show full bio"):
                    st.write(about)
            else:
                st.write(about)

        # Recent posts
        activity_log = connection.activity_log or []
        if activity_log:
            st.divider()
            st.write("**Recent Posts**")
            for i, activity in enumerate(activity_log[:5]):
                content = activity.get("content", "")
                url = activity.get("url") or activity.get("postUrl") or ""
                with st.container():
                    display = content[:300] + "..." if len(content) > 300 else content
                    st.markdown(f"_{display}_")
                    if url:
                        st.caption(f"[View post]({url})")
                    if i < min(len(activity_log), 5) - 1:
                        st.markdown("---")

        # Experience timeline
        experiences = _get_experiences(enrichment)
        if experiences:
            st.divider()
            st.write("**Experience**")

            for exp in experiences[:6]:
                title = exp.get("title", "")
                company = _exp_company(exp)
                if not title and not company:
                    continue

                label = f"**{title}**" if title else ""
                if company:
                    label += f" at {company}" if label else f"**{company}**"
                st.markdown(label)

                date_info = _exp_date_range(exp)
                duration = exp.get("duration", "")
                caption_parts = [p for p in [date_info, duration] if p]
                if caption_parts:
                    st.caption(" · ".join(caption_parts))

                desc = exp.get("description", "")
                if desc:
                    truncated = desc[:200] + "..." if len(desc) > 200 else desc
                    st.caption(truncated)

        # Skills
        skills = _get_skills(enrichment)
        if skills:
            st.divider()
            st.write("**Skills**")
            st.write(" · ".join(skills))

        # Education
        educations = _get_educations(enrichment)
        if educations:
            st.divider()
            st.write("**Education**")
            for edu in educations[:3]:
                school = edu.get("school") or edu.get("schoolName") or edu.get("school_name") or ""
                degree = edu.get("degree") or edu.get("degree_name") or ""
                field = edu.get("field_of_study") or edu.get("fieldOfStudy") or ""
                if school:
                    edu_line = f"**{school}**"
                    parts = [p for p in [degree, field] if p]
                    if parts:
                        edu_line += f" — {', '.join(parts)}"
                    st.markdown(edu_line)
                    date_range = edu.get("date_range", "")
                    if date_range:
                        st.caption(date_range)

        # Notes
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
