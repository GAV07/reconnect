"""Telegram Bot API integration for pipeline notifications."""

import json
import logging
import urllib.request
import urllib.error
import html

from src.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"
MAX_MESSAGE_LENGTH = 4096


def is_telegram_configured() -> bool:
    """Check if Telegram bot token and chat ID are set."""
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def send_pipeline_notification(results: dict) -> bool:
    """
    Send a pipeline digest notification via Telegram.

    Args:
        results: Pipeline results dict from run_daily_pipeline()

    Returns:
        True if message sent successfully
    """
    if not is_telegram_configured():
        logger.debug("Telegram not configured, skipping notification")
        return False

    try:
        # Check if this is a failure notification
        if "error" in results:
            error = results["error"]
            text = (
                "<b>Pipeline Failed</b>\n\n"
                f"Step: <code>{html.escape(str(error.get('step', 'unknown')))}</code>\n"
                f"Error: <code>{html.escape(str(error.get('message', 'unknown'))[:500])}</code>"
            )
            return _send_message(text)

        # Build success digest
        summary = _build_pipeline_summary(results)

        # If email digest was sent, skip the LLM action brief — just ping
        if results.get("email_digest", {}).get("sent"):
            digest_info = results["email_digest"]
            count = digest_info.get("contacts", 0)
            drafts = digest_info.get("drafts_generated", 0)
            full_message = (
                summary + "\n\n"
                f"<b>Email digest sent</b> — {count} contacts, "
                f"{drafts} draft messages.\n"
                "Check your email for today's action brief."
            )
        else:
            # Full LLM-generated action brief (fallback)
            action_summary = _build_action_summary()
            if action_summary:
                full_message = summary + "\n\n" + action_summary
            else:
                full_message = summary

        if len(full_message) > MAX_MESSAGE_LENGTH:
            full_message = full_message[:MAX_MESSAGE_LENGTH - 3] + "..."

        return _send_message(full_message)

    except Exception as e:
        logger.error("Failed to send Telegram notification: %s", e)
        return False


def send_failure_notification(error_step: str, error_message: str) -> bool:
    """
    Send a pipeline failure alert via Telegram.

    Args:
        error_step: The pipeline step that failed
        error_message: The error message

    Returns:
        True if message sent successfully
    """
    if not is_telegram_configured():
        return False

    text = (
        "<b>Pipeline Failed</b>\n\n"
        f"Step: <code>{html.escape(error_step)}</code>\n"
        f"Error: <code>{html.escape(error_message[:500])}</code>"
    )
    return _send_message(text)


def _build_pipeline_summary(results: dict) -> str:
    """Format pipeline metrics into a summary block."""
    lines = ["<b>Reconnect Daily Digest</b>"]

    # Import stats
    if imp := results.get("import"):
        lines.append(
            f"\nImport: {imp.get('imported', 0)} new, "
            f"{imp.get('updated', 0)} updated, "
            f"{imp.get('messages_processed', 0)} messages"
        )

    # Pre-scoring
    if pre := results.get("prescore"):
        lines.append(f"Pre-scored: {pre.get('scored', 0)} contacts")

    # Enrichment
    if enrich := results.get("enrich"):
        lines.append(
            f"Enriched: {enrich.get('success', 0)} ok, "
            f"{enrich.get('failed', 0)} failed"
        )

    # Full scoring
    if score := results.get("score"):
        lines.append(f"Scored: {score.get('scored', 0)} contacts")

    # Queue generation
    if queue := results.get("queue"):
        parts = [f"+{queue.get('added', 0)} added"]
        if queue.get("expired", 0) > 0:
            parts.append(f"{queue['expired']} expired")
        parts.append(f"{queue.get('excluded', 0)} excluded")
        lines.append("Queue: " + ", ".join(parts))

    # Sync
    if sync := results.get("sync"):
        if sync.get("error"):
            lines.append(f"Sync: failed ({str(sync['error'])[:50]})")
        else:
            lines.append("Sync: ok")

    return "\n".join(lines)


def _build_action_summary() -> str:
    """
    Build a concise, LLM-generated action brief from pending queue items.

    Falls back to a stats-only summary if OpenAI is unavailable.
    """
    try:
        from src.pipeline.queue_generator import get_pending_queue

        pending = get_pending_queue()
    except Exception as e:
        logger.warning("Could not fetch pending queue: %s", e)
        return ""

    if not pending:
        return ""

    # Cap at 15 contacts by priority score (already sorted by get_pending_queue)
    pending = pending[:15]

    # Build context for LLM — extract rich rubric data
    contact_lines = []
    channels = {"email": 0, "linkedin": 0}
    for queue_item, connection in pending:
        score = connection.reconnect_score or connection.pre_score or 0
        role = connection.current_role or "Unknown role"
        company = connection.current_company or ""
        role_str = f"{role} @ {company}" if company else role

        extras = []
        if connection.score_reasoning:
            try:
                reasoning = json.loads(connection.score_reasoning)
                # Top dimension scores
                if dims := reasoning.get("dimension_scores"):
                    if isinstance(dims, dict):
                        top_dims = sorted(dims.items(), key=lambda x: x[1], reverse=True)[:2]
                        extras.append("Top: " + ", ".join(f"{k} {v}" for k, v in top_dims))
                # Conversation hooks
                if hooks := reasoning.get("conversation_hooks"):
                    if isinstance(hooks, list) and hooks:
                        extras.append("Hooks: " + "; ".join(str(h) for h in hooks[:2]))
                # Key factors
                if kf := reasoning.get("key_factors"):
                    if isinstance(kf, list) and kf:
                        extras.append("Why: " + "; ".join(str(f) for f in kf[:2]))
            except (json.JSONDecodeError, TypeError):
                pass

        line = f"- {connection.name} | {role_str} | Score: {score:.0f}"
        if extras:
            line += " | " + " | ".join(extras)
        contact_lines.append(line)
        channels[queue_item.channel or "linkedin"] = channels.get(queue_item.channel or "linkedin", 0) + 1

    context = "\n".join(contact_lines)

    # Try LLM summary
    try:
        from src.config import settings as _settings

        if not _settings.openai_api_key:
            raise ValueError("No API key")

        from openai import OpenAI

        client = OpenAI(api_key=_settings.openai_api_key)
        response = client.chat.completions.create(
            model=_settings.openai_model,
            messages=[{
                "role": "user",
                "content": (
                    "You are a concise networking assistant. Write a daily action brief for a busy professional.\n\n"
                    "FORMAT (plain text, no markdown/HTML):\n"
                    "1. Top 3 people to reach out to today — for each, give their name and a specific "
                    "conversation opener based on the hooks provided\n"
                    "2. One line: queue summary (total pending, channels)\n\n"
                    "Be specific — use the conversation hooks and key factors to craft openers, "
                    "not generic 'catch up' suggestions.\n\n"
                    f"Pending contacts ({len(pending)} total, "
                    f"{channels.get('email', 0)} email / {channels.get('linkedin', 0)} LinkedIn):\n{context}"
                ),
            }],
            max_tokens=350,
            temperature=0.7,
        )
        brief = response.choices[0].message.content.strip()
        return f"<b>Action Brief</b>\n{html.escape(brief)}"

    except Exception as e:
        logger.debug("LLM summary unavailable (%s), using fallback", e)
        return _build_fallback_summary(pending, channels)


def _build_fallback_summary(
    pending: list[tuple], channels: dict[str, int]
) -> str:
    """Stats-only fallback when OpenAI is unavailable."""
    total = len(pending)

    lines = [f"<b>Pending Outreach: {total} contacts</b>"]

    channel_parts = []
    for ch, count in channels.items():
        if count > 0:
            channel_parts.append(f"{count} {ch}")
    if channel_parts:
        lines.append("Channels: " + ", ".join(channel_parts))

    # Top 3 contacts with conversation hooks
    for _, conn in pending[:3]:
        name = html.escape(conn.name or "Unknown")
        hook = ""
        if conn.score_reasoning:
            try:
                reasoning = json.loads(conn.score_reasoning)
                hooks = reasoning.get("conversation_hooks", [])
                if isinstance(hooks, list) and hooks:
                    hook = f" — {html.escape(str(hooks[0]))}"
            except (json.JSONDecodeError, TypeError):
                pass
        lines.append(f"• {name}{hook}")

    return "\n".join(lines)


def _send_message(text: str) -> bool:
    """
    Send a message via Telegram Bot API using HTML parse mode.

    Args:
        text: HTML-formatted message text

    Returns:
        True if sent successfully
    """
    url = f"{TELEGRAM_API_BASE.format(token=settings.telegram_bot_token)}/sendMessage"
    payload = json.dumps({
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        import ssl
        import certifi

        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
            result = json.loads(resp.read())
            if not result.get("ok"):
                logger.error("Telegram API error: %s", result)
                return False
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error("Telegram HTTP %d: %s", e.code, body[:200])
        return False
    except Exception as e:
        logger.error("Telegram send failed: %s", e)
        return False
