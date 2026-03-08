"""Email digest — actionable HTML email with token-based action buttons.

No pre-drafted messages (saves tokens until user commits).
Action buttons hit Supabase Edge Functions — work from any device.
"""

import json
import logging
from datetime import datetime
from html import escape
from typing import Any

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection, OutreachQueueItem, UserProfile

logger = logging.getLogger(__name__)


def _get_digest_contacts(top_n: int) -> list[tuple[OutreachQueueItem, Connection]]:
    """Fetch pending queue items with their connections.

    Returns:
        List of (queue_item, connection) tuples sorted by priority.
        No draft generation — drafts are generated on-demand in the PWA.
    """
    from src.pipeline.queue_generator import get_pending_queue

    pending = get_pending_queue()
    if not pending:
        return []

    return pending


def _extract_why_today(conn: Connection, queue_item: OutreachQueueItem) -> str:
    """Extract a 'Why Today' hook from score_reasoning or why_today field."""
    # Use explicit why_today if set
    if queue_item.why_today:
        return queue_item.why_today

    # Extract from score_reasoning
    if conn.score_reasoning:
        try:
            reasoning = json.loads(conn.score_reasoning)
            hooks = reasoning.get("conversation_hooks", [])
            if isinstance(hooks, list) and hooks:
                return str(hooks[0])
            factors = reasoning.get("key_factors", [])
            if isinstance(factors, list) and factors:
                return str(factors[0])
        except (json.JSONDecodeError, TypeError):
            pass

    return ""


def _get_data_health_stats() -> dict[str, int]:
    """Compute data health statistics for the digest."""
    from sqlmodel import func, select

    stats = {
        "need_email": 0,
        "need_enrichment": 0,
        "need_rescoring": 0,
    }

    with get_session() as session:
        # Contacts with score but no email
        stats["need_email"] = session.exec(
            select(func.count(Connection.id))
            .where(Connection.reconnect_score.isnot(None))
            .where(Connection.reconnect_score >= settings.min_queue_score)
            .where(
                (Connection.email.is_(None)) | (Connection.email == "")
            )
        ).one()

        # Contacts with pre_score but not enriched
        stats["need_enrichment"] = session.exec(
            select(func.count(Connection.id))
            .where(Connection.pre_score.isnot(None))
            .where(Connection.enriched_at.is_(None))
        ).one()

        # Enriched contacts without a score
        stats["need_rescoring"] = session.exec(
            select(func.count(Connection.id))
            .where(Connection.enriched_at.isnot(None))
            .where(Connection.reconnect_score.is_(None))
        ).one()

    return stats


def _get_skip_pattern_insight() -> str | None:
    """Analyze recent skips for a pattern insight."""
    from sqlmodel import select

    with get_session() as session:
        # Get recently skipped queue items
        skipped = session.exec(
            select(OutreachQueueItem)
            .where(OutreachQueueItem.status == "skipped")
            .where(OutreachQueueItem.reviewed_at.isnot(None))
            .order_by(OutreachQueueItem.reviewed_at.desc())
            .limit(20)
        ).all()

        if len(skipped) < 5:
            return None

        # Count companies/roles of skipped contacts
        company_counts: dict[str, int] = {}
        for item in skipped:
            conn = session.get(Connection, item.connection_id)
            if conn and conn.current_company:
                company_counts[conn.current_company] = company_counts.get(conn.current_company, 0) + 1

        # Find dominant skip pattern
        if company_counts:
            top_company, count = max(company_counts.items(), key=lambda x: x[1])
            pct = count / len(skipped) * 100
            if pct >= 40:
                return f"You skipped {pct:.0f}% of {escape(top_company)} contacts this week"

    return None


def _build_digest_html(
    contacts: list[tuple[OutreachQueueItem, Connection]],
    pipeline_results: dict[str, Any],
    top_n: int,
) -> str:
    """Build the HTML email body with action buttons and data health section."""
    today = datetime.now().strftime("%B %-d, %Y")
    total = len(contacts)

    # Pipeline stats one-liner
    stats_parts = []
    if imp := pipeline_results.get("import"):
        stats_parts.append(f"{imp.get('imported', 0)} imported")
    if enrich := pipeline_results.get("enrich"):
        stats_parts.append(f"{enrich.get('success', 0)} enriched")
    if score := pipeline_results.get("score"):
        stats_parts.append(f"{score.get('scored', 0)} scored")
    if queue := pipeline_results.get("queue"):
        stats_parts.append(f"+{queue.get('added', 0)} queued")
    stats_line = " &middot; ".join(stats_parts) if stats_parts else ""

    featured = contacts[:top_n]
    remaining = contacts[top_n:]

    # Generate action tokens for featured contacts
    from src.api.tokens import create_action_tokens, create_feedback_token

    # --- Build featured cards ---
    cards_html = ""
    for queue_item, conn in featured:
        name = escape(conn.name or "Unknown")
        score = conn.reconnect_score or conn.pre_score or 0
        role = escape(conn.current_role or "")
        company = escape(conn.current_company or "")
        role_line = f"{role} @ {company}" if company else role
        linkedin_url = conn.linkedin_url or ""

        # Why Today hook
        why_today = _extract_why_today(conn, queue_item)
        why_html = f'<div style="color:#1a7f37;font-size:13px;margin:6px 0;"><strong>WHY:</strong> {escape(why_today)}</div>' if why_today else ""

        # Name linked to LinkedIn
        name_html = f'<a href="{escape(linkedin_url)}" style="color:#0a66c2;text-decoration:none;font-weight:bold;font-size:17px;">{name}</a>' if linkedin_url else f'<span style="font-weight:bold;font-size:17px;">{name}</span>'

        # Token-based action buttons
        buttons_html = ""
        if queue_item.id and conn.id:
            try:
                urls = create_action_tokens(queue_item.id, conn.id)
                buttons_html = f'''<div style="margin-top:10px;">
                    <a href="{escape(urls['approve'])}" style="display:inline-block;background:#1a7f37;color:#ffffff;text-decoration:none;padding:8px 16px;border-radius:4px;font-size:13px;font-weight:bold;margin-right:6px;">Reach Out &#9654;</a>
                    <a href="{escape(urls['skip'])}" style="display:inline-block;background:#6c757d;color:#ffffff;text-decoration:none;padding:8px 16px;border-radius:4px;font-size:13px;margin-right:6px;">Skip</a>
                    <a href="{escape(urls['snooze'])}" style="display:inline-block;background:#f0ad4e;color:#ffffff;text-decoration:none;padding:8px 16px;border-radius:4px;font-size:13px;">Snooze 3d</a>
                </div>'''
            except Exception as e:
                logger.warning("Failed to create action tokens for %s: %s", conn.name, e)

        cards_html += f'''
        <div style="background:#ffffff;border:1px solid #e0e0e0;border-radius:8px;padding:16px 18px;margin-bottom:12px;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>{name_html}<div style="color:#555;font-size:14px;margin:2px 0;">{role_line}</div></div>
                <div style="background:#e8f4fd;color:#0a66c2;font-weight:bold;font-size:14px;padding:4px 10px;border-radius:12px;white-space:nowrap;">Score: {score:.0f}</div>
            </div>
            {why_html}
            {buttons_html}
        </div>
        '''

    # --- Remaining contacts compact list ---
    remaining_html = ""
    if remaining:
        remaining_items = ""
        for queue_item, conn in remaining:
            name = escape(conn.name or "Unknown")
            score = conn.reconnect_score or conn.pre_score or 0
            role_line = escape(conn.current_role or "")
            if conn.current_company:
                role_line += f" @ {escape(conn.current_company)}"
            remaining_items += f'<div style="padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:14px;"><strong>{name}</strong> <span style="color:#888;">({score:.0f})</span> <span style="color:#555;">{role_line}</span></div>'

        remaining_html = f'''
        <div style="margin-top:16px;padding-top:12px;border-top:1px solid #eee;">
            <div style="font-weight:bold;font-size:14px;color:#333;margin-bottom:8px;">+{len(remaining)} more in queue</div>
            {remaining_items}
        </div>'''

    # --- Data Health Section ---
    health_stats = _get_data_health_stats()
    skip_insight = _get_skip_pattern_insight()

    health_items = []
    if health_stats["need_email"] > 0:
        health_items.append(f'<div style="padding:4px 0;">&bull; {health_stats["need_email"]} high-priority contacts need email addresses</div>')
    if health_stats["need_enrichment"] > 0:
        health_items.append(f'<div style="padding:4px 0;">&bull; {health_stats["need_enrichment"]} contacts could score better with enrichment</div>')
    if health_stats["need_rescoring"] > 0:
        health_items.append(f'<div style="padding:4px 0;">&bull; {health_stats["need_rescoring"]} enriched contacts need scoring</div>')
    if skip_insight:
        health_items.append(f'<div style="padding:4px 0;">&bull; {skip_insight}</div>')

    health_html = ""
    if health_items:
        health_content = "\n".join(health_items)
        health_html = f'''
        <div style="background:#f8f9fa;border:1px solid #e9ecef;border-radius:8px;padding:16px 18px;margin-top:20px;">
            <div style="font-weight:bold;font-size:15px;color:#333;margin-bottom:8px;">Your Network Data</div>
            <div style="font-size:13px;color:#555;line-height:1.6;">
                {health_content}
            </div>
        </div>'''

    # --- Feedback CTA ---
    feedback_html = ""
    try:
        rating_buttons = ""
        for i in range(1, 6):
            url = create_feedback_token(rating=i)
            rating_buttons += f'<a href="{escape(url)}" style="display:inline-block;background:#ffffff;border:1px solid #ddd;color:#333;text-decoration:none;padding:8px 14px;border-radius:4px;font-size:16px;margin:0 3px;">{i}</a>'
        feedback_html = f'''
        <div style="text-align:center;margin-top:20px;padding-top:16px;border-top:1px solid #eee;">
            <div style="font-size:14px;color:#666;margin-bottom:8px;">Was today's digest useful?</div>
            <div>{rating_buttons}</div>
        </div>'''
    except Exception as e:
        logger.warning("Failed to create feedback tokens: %s", e)

    # --- PWA link ---
    pwa_link = settings.pwa_url.rstrip("/") + "/#/queue" if settings.pwa_url else "http://localhost:8501"

    # --- Assemble full email ---
    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:20px;">

    <div style="background:#0a66c2;color:#ffffff;padding:18px 20px;border-radius:8px 8px 0 0;">
        <div style="font-size:20px;font-weight:bold;">Reconnect</div>
        <div style="font-size:14px;opacity:0.9;margin-top:4px;">{today} &mdash; {total} contact{"s" if total != 1 else ""} to reach today</div>
        {f'<div style="font-size:13px;opacity:0.8;margin-top:4px;">{stats_line}</div>' if stats_line else ""}
    </div>

    <div style="background:#ffffff;padding:20px;border-radius:0 0 8px 8px;border:1px solid #e0e0e0;border-top:none;">
        {cards_html}
        {remaining_html}

        <div style="text-align:center;margin-top:20px;padding-top:16px;border-top:1px solid #eee;">
            <a href="{escape(pwa_link)}" style="display:inline-block;background:#0a66c2;color:#ffffff;text-decoration:none;padding:10px 24px;border-radius:6px;font-size:14px;font-weight:bold;">View Full Queue ({total} more) &rarr;</a>
        </div>

        {health_html}
        {feedback_html}
    </div>

    <div style="text-align:center;margin-top:16px;color:#999;font-size:12px;">
        Sent by Reconnect &middot; <a href="{escape(pwa_link)}" style="color:#999;">Open app</a>
    </div>

</div>
</body>
</html>'''

    return html


def send_digest_email(pipeline_results: dict[str, Any]) -> dict[str, Any]:
    """Build and send the daily digest email.

    Args:
        pipeline_results: Results dict from run_daily_pipeline()

    Returns:
        Dict with sent status, recipient, and contact count
    """
    from src.integrations.gmail import get_user_email, is_gmail_configured, send_html_email

    if not is_gmail_configured():
        return {"sent": False, "reason": "Gmail not configured"}

    # Determine recipient
    recipient = settings.digest_recipient_email or get_user_email()
    if not recipient:
        return {"sent": False, "reason": "No recipient email available"}

    top_n = settings.digest_top_n

    try:
        contacts = _get_digest_contacts(top_n)
    except Exception as e:
        logger.error("Failed to get digest contacts: %s", e)
        return {"sent": False, "reason": f"Contact fetch failed: {e}"}

    if not contacts:
        return {"sent": False, "reason": "No pending contacts"}

    # Build subject: "Reconnect Mar 4: Sarah, Mike, Lisa + 12 more"
    today = datetime.now().strftime("%b %-d")
    top_names = [conn.name.split()[0] for _, conn in contacts[:3] if conn.name]
    names_str = ", ".join(top_names)
    extra = len(contacts) - len(top_names)
    if extra > 0:
        subject = f"Reconnect {today}: {names_str} + {extra} more"
    else:
        subject = f"Reconnect {today}: {names_str}"

    html_body = _build_digest_html(contacts, pipeline_results, top_n)

    try:
        result = send_html_email(recipient, subject, html_body)
        return {
            "sent": True,
            "recipient": recipient,
            "contacts": len(contacts),
            "featured": min(top_n, len(contacts)),
            "message_id": result.get("message_id"),
        }
    except Exception as e:
        logger.error("Failed to send digest email: %s", e)
        return {"sent": False, "reason": f"Send failed: {e}"}
