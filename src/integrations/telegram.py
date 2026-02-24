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

        # Build action-oriented summary of pending contacts
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
        lines.append(
            f"Queue: +{queue.get('added', 0)} added, "
            f"{queue.get('excluded', 0)} excluded"
        )

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

    # Build context for LLM
    contact_lines = []
    channels = {"email": 0, "linkedin": 0}
    for queue_item, connection in pending:
        score = connection.reconnect_score or connection.pre_score or 0
        role = connection.current_role or "Unknown role"
        company = connection.current_company or ""
        role_str = f"{role} @ {company}" if company else role

        factors = ""
        if connection.score_reasoning:
            try:
                reasoning = json.loads(connection.score_reasoning)
                if kf := reasoning.get("key_factors"):
                    if isinstance(kf, list):
                        factors = "; ".join(str(f) for f in kf[:2])
            except (json.JSONDecodeError, TypeError):
                pass

        line = f"- {connection.name} | {role_str} | Score: {score:.0f}"
        if factors:
            line += f" | {factors}"
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
                    "You are a concise networking assistant. Given these pending outreach contacts, "
                    "write a ~500 character action brief for a busy professional. "
                    "Highlight the top 2-3 people to prioritize and why. Be specific with names and reasons. "
                    "Use plain text, no markdown or HTML.\n\n"
                    f"Pending contacts ({len(pending)} total):\n{context}"
                ),
            }],
            max_tokens=200,
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
    top_names = [conn.name for _, conn in pending[:3]]

    lines = [f"<b>Pending Outreach: {total} contacts</b>"]

    channel_parts = []
    for ch, count in channels.items():
        if count > 0:
            channel_parts.append(f"{count} {ch}")
    if channel_parts:
        lines.append("Channels: " + ", ".join(channel_parts))

    if top_names:
        lines.append("Top: " + ", ".join(html.escape(n) for n in top_names))

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
