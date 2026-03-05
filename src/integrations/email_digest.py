"""Email digest — actionable HTML email with draft messages and LinkedIn links."""

import json
import logging
from datetime import datetime
from html import escape
from typing import Any, Optional
from urllib.parse import quote

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection, OutreachQueueItem, UserProfile

logger = logging.getLogger(__name__)


def _get_digest_contacts(top_n: int) -> list[tuple[OutreachQueueItem, Connection]]:
    """
    Fetch pending queue and pre-generate drafts for top N contacts.

    Returns:
        List of (queue_item, connection) tuples sorted by priority.
        The first top_n items will have draft_message populated.
    """
    from src.pipeline.queue_generator import get_pending_queue

    pending = get_pending_queue()
    if not pending:
        return []

    # Generate drafts for top N that don't already have one
    with get_session() as session:
        user_profile = session.get(UserProfile, 1)

    for queue_item, connection in pending[:top_n]:
        if queue_item.draft_message:
            continue
        try:
            from src.llm.prose import generate_outreach_message

            channel = queue_item.channel or "linkedin"
            draft = generate_outreach_message(connection, user_profile, channel=channel)
            queue_item.draft_message = draft

            # Persist back so the app stays in sync
            with get_session() as session:
                db_item = session.get(OutreachQueueItem, queue_item.id)
                if db_item:
                    db_item.draft_message = draft
                    session.add(db_item)
        except Exception as e:
            logger.warning("Draft generation failed for %s: %s", connection.name, e)

    return pending


def _build_digest_html(
    contacts: list[tuple[OutreachQueueItem, Connection]],
    pipeline_results: dict[str, Any],
    top_n: int,
) -> str:
    """Build the HTML email body with featured cards and compact rows."""
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

    # --- Build featured cards ---
    cards_html = ""
    for queue_item, conn in featured:
        name = escape(conn.name or "Unknown")
        score = conn.reconnect_score or conn.pre_score or 0
        role = escape(conn.current_role or "")
        company = escape(conn.current_company or "")
        role_line = f"{role} @ {company}" if company else role
        linkedin_url = conn.linkedin_url or ""
        email_addr = conn.email or ""

        # Extract conversation hook from score_reasoning
        hook = ""
        if conn.score_reasoning:
            try:
                reasoning = json.loads(conn.score_reasoning)
                hooks = reasoning.get("conversation_hooks", [])
                if isinstance(hooks, list) and hooks:
                    hook = escape(str(hooks[0]))
            except (json.JSONDecodeError, TypeError):
                pass

        # Name linked to LinkedIn
        name_html = f'<a href="{escape(linkedin_url)}" style="color:#0a66c2;text-decoration:none;font-weight:bold;font-size:18px;">{name}</a>' if linkedin_url else f'<span style="font-weight:bold;font-size:18px;">{name}</span>'

        # Draft message box
        draft_html = ""
        if queue_item.draft_message:
            draft_text = escape(queue_item.draft_message)
            draft_html = f'''
            <div style="background:#f8f9fa;border:1px solid #e9ecef;border-radius:6px;padding:12px 14px;margin:10px 0;font-size:14px;line-height:1.5;color:#333;white-space:pre-wrap;">{draft_text}</div>
            '''

        # Action buttons
        buttons = []
        if linkedin_url:
            dm_url = f"{linkedin_url.rstrip('/')}/overlay/new-message/"
            buttons.append(
                f'<a href="{escape(dm_url)}" style="display:inline-block;background:#0a66c2;color:#ffffff;text-decoration:none;padding:8px 16px;border-radius:4px;font-size:13px;font-weight:bold;margin-right:8px;">Message on LinkedIn</a>'
            )
            buttons.append(
                f'<a href="{escape(linkedin_url)}" style="display:inline-block;background:#ffffff;color:#0a66c2;text-decoration:none;padding:8px 16px;border-radius:4px;font-size:13px;border:1px solid #0a66c2;margin-right:8px;">View Profile</a>'
            )
        if email_addr and queue_item.draft_message:
            subject = quote(f"Reconnecting — {conn.name or ''}")
            body = quote(queue_item.draft_message)
            buttons.append(
                f'<a href="mailto:{escape(email_addr)}?subject={subject}&body={body}" style="display:inline-block;background:#ffffff;color:#333;text-decoration:none;padding:8px 16px;border-radius:4px;font-size:13px;border:1px solid #ccc;">Send Email</a>'
            )

        buttons_html = "\n".join(buttons) if buttons else ""

        hook_html = f'<div style="color:#666;font-size:13px;font-style:italic;margin:6px 0;">{hook}</div>' if hook else ""

        cards_html += f'''
        <div style="background:#ffffff;border:1px solid #e0e0e0;border-radius:8px;padding:16px 18px;margin-bottom:14px;">
            {name_html}
            <div style="color:#555;font-size:14px;margin:4px 0;">{role_line}</div>
            <div style="color:#888;font-size:13px;">Score: {score:.0f}</div>
            {hook_html}
            {draft_html}
            <div style="margin-top:10px;">{buttons_html}</div>
        </div>
        '''

    # --- Build remaining contacts compact rows ---
    rows_html = ""
    if remaining:
        row_items = ""
        for queue_item, conn in remaining:
            name = escape(conn.name or "Unknown")
            score = conn.reconnect_score or conn.pre_score or 0
            role = escape(conn.current_role or "")
            company = escape(conn.current_company or "")
            role_line = f"{role} @ {company}" if company else role
            linkedin_url = conn.linkedin_url or ""

            name_html = f'<a href="{escape(linkedin_url)}" style="color:#0a66c2;text-decoration:none;font-weight:bold;">{name}</a>' if linkedin_url else f"<b>{name}</b>"
            row_items += f'''
            <tr>
                <td style="padding:8px 10px;border-bottom:1px solid #f0f0f0;">{name_html}</td>
                <td style="padding:8px 10px;border-bottom:1px solid #f0f0f0;color:#888;font-size:13px;">{score:.0f}</td>
                <td style="padding:8px 10px;border-bottom:1px solid #f0f0f0;color:#555;font-size:13px;">{role_line}</td>
            </tr>
            '''

        rows_html = f'''
        <div style="margin-top:24px;">
            <div style="font-weight:bold;font-size:15px;color:#333;margin-bottom:8px;">More contacts ready for outreach</div>
            <table style="width:100%;border-collapse:collapse;">
                <tr style="background:#f8f9fa;">
                    <th style="text-align:left;padding:6px 10px;font-size:13px;color:#666;">Name</th>
                    <th style="text-align:left;padding:6px 10px;font-size:13px;color:#666;">Score</th>
                    <th style="text-align:left;padding:6px 10px;font-size:13px;color:#666;">Role</th>
                </tr>
                {row_items}
            </table>
        </div>
        '''

    # --- Assemble full email ---
    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:20px;">

    <div style="background:#0a66c2;color:#ffffff;padding:18px 20px;border-radius:8px 8px 0 0;">
        <div style="font-size:20px;font-weight:bold;">Reconnect</div>
        <div style="font-size:14px;opacity:0.9;margin-top:4px;">{today} &mdash; {total} contact{"s" if total != 1 else ""} ready for outreach</div>
        {f'<div style="font-size:13px;opacity:0.8;margin-top:4px;">{stats_line}</div>' if stats_line else ""}
    </div>

    <div style="background:#ffffff;padding:20px;border-radius:0 0 8px 8px;border:1px solid #e0e0e0;border-top:none;">
        {cards_html}
        {rows_html}

        <div style="text-align:center;margin-top:24px;padding-top:16px;border-top:1px solid #eee;">
            <a href="http://localhost:8501" style="display:inline-block;background:#0a66c2;color:#ffffff;text-decoration:none;padding:10px 24px;border-radius:6px;font-size:14px;font-weight:bold;">Open Review Queue</a>
        </div>
    </div>

    <div style="text-align:center;margin-top:16px;color:#999;font-size:12px;">
        Sent by Reconnect &middot; <a href="http://localhost:8501" style="color:#999;">Manage settings</a>
    </div>

</div>
</body>
</html>'''

    return html


def send_digest_email(pipeline_results: dict[str, Any]) -> dict[str, Any]:
    """
    Public entry point — build and send the daily digest email.

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
            "drafts_generated": sum(1 for qi, _ in contacts[:top_n] if qi.draft_message),
            "message_id": result.get("message_id"),
        }
    except Exception as e:
        logger.error("Failed to send digest email: %s", e)
        return {"sent": False, "reason": f"Send failed: {e}"}
