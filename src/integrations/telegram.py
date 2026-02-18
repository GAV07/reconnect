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

        # Get pending queue items for contact cards
        contact_cards = _build_contact_cards()

        if not contact_cards:
            return _send_message(summary)

        # Try single message first
        full_message = summary + "\n\n" + "\n\n".join(contact_cards)
        if len(full_message) <= MAX_MESSAGE_LENGTH:
            return _send_message(full_message)

        # Split: send summary first, then batch contact cards
        _send_message(summary)

        batch = ""
        for card in contact_cards:
            if batch and len(batch) + len(card) + 2 > MAX_MESSAGE_LENGTH:
                _send_message(batch)
                batch = ""
            batch = batch + "\n\n" + card if batch else card

        if batch:
            _send_message(batch)

        return True

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


def _build_contact_cards() -> list[str]:
    """Build formatted cards for all pending queue items."""
    try:
        from src.pipeline.queue_generator import get_pending_queue

        pending = get_pending_queue()
    except Exception as e:
        logger.warning("Could not fetch pending queue: %s", e)
        return []

    cards = []
    for queue_item, connection in pending:
        card = _build_contact_card(queue_item, connection)
        if card:
            cards.append(card)
    return cards


def _build_contact_card(queue_item, connection) -> str:
    """
    Format one contact into a card with name, role, score, key factors,
    conversation hooks, and a draft message preview.
    """
    name = html.escape(connection.name or "Unknown")
    role = html.escape(connection.current_role or "")
    company = html.escape(connection.current_company or "")

    score = connection.reconnect_score or connection.pre_score or 0
    channel = queue_item.channel or "linkedin"

    lines = [f"<b>{name}</b>"]
    if role or company:
        role_line = f"{role}" if role else ""
        if company:
            role_line += f" @ {company}" if role_line else company
        lines.append(role_line)
    lines.append(f"Score: {score:.0f} | {channel}")

    # Parse score_reasoning for key_factors and conversation_hooks
    if connection.score_reasoning:
        try:
            reasoning = json.loads(connection.score_reasoning)
            if factors := reasoning.get("key_factors"):
                if isinstance(factors, list):
                    lines.append("Factors: " + ", ".join(str(f) for f in factors[:3]))
            if hooks := reasoning.get("conversation_hooks"):
                if isinstance(hooks, list):
                    lines.append("Hooks: " + ", ".join(str(h) for h in hooks[:2]))
        except (json.JSONDecodeError, TypeError):
            pass

    # Draft message preview (first 150 chars)
    if queue_item.draft_message:
        preview = queue_item.draft_message[:150]
        if len(queue_item.draft_message) > 150:
            preview += "..."
        lines.append(f"<i>{html.escape(preview)}</i>")

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
