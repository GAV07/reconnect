"""Dashboard page with network visualizations."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from sqlmodel import select, func

from src.database.engine import get_session
from src.database.models import Connection, OutreachQueueItem, PipelineRun


def render_dashboard_page():
    """Render the dashboard page with 4 chart sections."""
    st.title("Dashboard")
    st.caption("Visual overview of your network and outreach activity")

    _render_score_distribution()
    st.divider()
    _render_outreach_funnel()
    st.divider()
    _render_network_composition()
    st.divider()
    _render_activity_timeline()



def _render_score_distribution():
    """Bar chart of contacts by score range."""
    st.subheader("Score Distribution")

    with get_session() as session:
        connections = session.exec(
            select(Connection.reconnect_score)
            .where(Connection.reconnect_score.isnot(None))
        ).all()

    if not connections:
        st.info("No scored contacts yet. Run the pipeline to score contacts.")
        return

    # Bucket scores into ranges
    buckets = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
    for score in connections:
        if score < 20:
            buckets["0-20"] += 1
        elif score < 40:
            buckets["20-40"] += 1
        elif score < 60:
            buckets["40-60"] += 1
        elif score < 80:
            buckets["60-80"] += 1
        else:
            buckets["80-100"] += 1

    fig = px.bar(
        x=list(buckets.keys()),
        y=list(buckets.values()),
        labels={"x": "Score Range", "y": "Contacts"},
        color=list(buckets.values()),
        color_continuous_scale="Blues",
    )
    fig.update_layout(showlegend=False, coloraxis_showscale=False, height=300)
    st.plotly_chart(fig, use_container_width=True)


def _render_outreach_funnel():
    """Funnel chart: Total → Scored → Queued → Sent → Replied."""
    st.subheader("Outreach Funnel")

    with get_session() as session:
        total = session.exec(select(func.count(Connection.id))).one()
        scored = session.exec(
            select(func.count(Connection.id))
            .where(Connection.reconnect_score.isnot(None))
        ).one()
        queued = session.exec(select(func.count(OutreachQueueItem.id))).one()
        sent = session.exec(
            select(func.count(OutreachQueueItem.id))
            .where(OutreachQueueItem.status == "sent")
        ).one()

    if total == 0:
        st.info("No contacts imported yet.")
        return

    # Check for replied count in outreach_log
    try:
        from src.database.models import OutreachLog
        with get_session() as session:
            replied = session.exec(
                select(func.count(OutreachLog.id))
                .where(OutreachLog.outcome == "replied")
            ).one()
    except Exception:
        replied = 0

    stages = ["Total Contacts", "Scored", "Queued", "Sent", "Replied"]
    values = [total, scored, queued, sent, replied]

    fig = go.Figure(go.Funnel(
        y=stages,
        x=values,
        textinfo="value+percent initial",
    ))
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)


def _render_network_composition():
    """Two-column: pie chart of top companies + bar chart of role keywords."""
    st.subheader("Network Composition")

    with get_session() as session:
        # Top companies
        companies = session.exec(
            select(Connection.current_company, func.count(Connection.id).label("cnt"))
            .where(Connection.current_company.isnot(None))
            .where(Connection.current_company != "")
            .group_by(Connection.current_company)
            .order_by(func.count(Connection.id).desc())
            .limit(10)
        ).all()

        # Roles
        roles = session.exec(
            select(Connection.current_role)
            .where(Connection.current_role.isnot(None))
            .where(Connection.current_role != "")
        ).all()

    if not companies and not roles:
        st.info("No enriched contacts yet. Enrich contacts to see network composition.")
        return

    col1, col2 = st.columns(2)

    with col1:
        if companies:
            company_names = [row[0] for row in companies]
            company_counts = [row[1] for row in companies]
            fig = px.pie(
                names=company_names,
                values=company_counts,
                title="Top 10 Companies",
            )
            fig.update_layout(height=350, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No company data available.")

    with col2:
        if roles:
            # Extract role keywords
            keywords = [
                "founder", "ceo", "cto", "coo", "vp", "director",
                "manager", "engineer", "developer", "designer",
                "analyst", "consultant", "product", "marketing", "sales",
            ]
            keyword_counts = {}
            for (role,) in roles:
                role_lower = role.lower()
                for kw in keywords:
                    if kw in role_lower:
                        keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

            if keyword_counts:
                sorted_kw = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:12]
                fig = px.bar(
                    x=[c for _, c in sorted_kw],
                    y=[k.title() for k, _ in sorted_kw],
                    orientation="h",
                    labels={"x": "Count", "y": "Role Keyword"},
                    title="Role Keywords",
                )
                fig.update_layout(height=350, yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No recognizable role keywords found.")
        else:
            st.info("No role data available.")


def _render_activity_timeline():
    """Two-column: messages sent per week + pipeline runs per day."""
    st.subheader("Activity Timeline")

    col1, col2 = st.columns(2)

    with col1:
        # Messages sent per week
        with get_session() as session:
            sent_items = session.exec(
                select(OutreachQueueItem.sent_at)
                .where(OutreachQueueItem.sent_at.isnot(None))
                .order_by(OutreachQueueItem.sent_at)
            ).all()

        if not sent_items:
            st.info("No messages sent yet.")
        else:
            from datetime import datetime, timedelta
            import collections

            weekly = collections.Counter()
            for (sent_at,) in sent_items:
                # ISO week start (Monday)
                week_start = sent_at - timedelta(days=sent_at.weekday())
                week_key = week_start.strftime("%Y-%m-%d")
                weekly[week_key] += 1

            sorted_weeks = sorted(weekly.items())
            fig = px.line(
                x=[w for w, _ in sorted_weeks],
                y=[c for _, c in sorted_weeks],
                labels={"x": "Week", "y": "Messages Sent"},
                title="Messages Sent per Week",
                markers=True,
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Pipeline runs per day (completed vs failed)
        with get_session() as session:
            runs = session.exec(
                select(PipelineRun.started_at, PipelineRun.status)
                .order_by(PipelineRun.started_at)
            ).all()

        if not runs:
            st.info("No pipeline runs recorded yet.")
        else:
            import collections

            daily_completed = collections.Counter()
            daily_failed = collections.Counter()

            for started_at, status in runs:
                day_key = started_at.strftime("%Y-%m-%d")
                if status == "failed":
                    daily_failed[day_key] += 1
                else:
                    daily_completed[day_key] += 1

            all_days = sorted(set(list(daily_completed.keys()) + list(daily_failed.keys())))

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=all_days,
                y=[daily_completed.get(d, 0) for d in all_days],
                name="Completed",
                marker_color="#2ecc71",
            ))
            fig.add_trace(go.Bar(
                x=all_days,
                y=[daily_failed.get(d, 0) for d in all_days],
                name="Failed",
                marker_color="#e74c3c",
            ))
            fig.update_layout(
                barmode="stack",
                height=300,
                title="Pipeline Runs per Day",
                xaxis_title="Date",
                yaxis_title="Runs",
            )
            st.plotly_chart(fig, use_container_width=True)
