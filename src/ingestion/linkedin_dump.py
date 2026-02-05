"""LinkedIn data dump analyzer for Reconnect.

Handles full LinkedIn data export ZIPs containing multiple CSVs:
- Connections.csv: Contact list with connection dates
- Messages.csv: Message history for conversation analysis
"""

import csv
import hashlib
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from openai import OpenAI
from sqlmodel import select
from thefuzz import fuzz

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection, ImportBatch


@dataclass
class ExtractedDump:
    """Paths to extracted LinkedIn dump files."""

    connections_path: Optional[Path] = None
    messages_path: Optional[Path] = None
    profile_path: Optional[Path] = None
    positions_path: Optional[Path] = None
    skills_path: Optional[Path] = None
    reactions_path: Optional[Path] = None
    comments_path: Optional[Path] = None
    extract_dir: Optional[Path] = None


@dataclass
class MessageStats:
    """Aggregated message statistics for a contact."""

    contact_name: str
    conversation_id: str
    message_count: int = 0
    last_message_date: Optional[datetime] = None
    first_sender: Optional[str] = None  # "user" | "contact"
    last_messages: list[dict] = field(default_factory=list)  # For LLM summary


@dataclass
class DumpImportResult:
    """Result of importing a LinkedIn dump."""

    batch_id: str
    connections_imported: int = 0
    connections_updated: int = 0
    new_connection_ids: list[str] = field(default_factory=list)
    messages_processed: int = 0
    conversations_summarized: int = 0
    errors: list[str] = field(default_factory=list)


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def extract_linkedin_dump(zip_path: Path, extract_to: Optional[Path] = None) -> ExtractedDump:
    """
    Extract LinkedIn data export ZIP and return paths to relevant CSVs.

    Args:
        zip_path: Path to the LinkedIn export ZIP file
        extract_to: Optional directory to extract to (uses temp dir if not specified)

    Returns:
        ExtractedDump with paths to found CSV files
    """
    if extract_to is None:
        extract_to = zip_path.parent / "linkedin_extract"

    extract_to.mkdir(parents=True, exist_ok=True)

    result = ExtractedDump(extract_dir=extract_to)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)

    # Find the relevant CSV files (LinkedIn nests them in subdirs)
    for csv_file in extract_to.rglob("*.csv"):
        name_lower = csv_file.name.lower()
        if "connection" in name_lower:
            result.connections_path = csv_file
        elif "message" in name_lower:
            result.messages_path = csv_file
        elif "profile" in name_lower and "position" not in name_lower:
            result.profile_path = csv_file
        elif "position" in name_lower:
            result.positions_path = csv_file
        elif "skill" in name_lower:
            result.skills_path = csv_file
        elif "reaction" in name_lower:
            result.reactions_path = csv_file
        elif "comment" in name_lower:
            result.comments_path = csv_file

    return result


def parse_linkedin_date(date_str: str) -> Optional[datetime]:
    """Parse various LinkedIn date formats."""
    if not date_str or not date_str.strip():
        return None

    date_str = date_str.strip()
    formats = [
        "%d %b %Y",  # 15 Jan 2024
        "%b %d, %Y",  # Jan 15, 2024
        "%Y-%m-%d",  # 2024-01-15
        "%Y-%m-%d %H:%M:%S",  # 2024-01-15 10:30:00
        "%m/%d/%Y",  # 01/15/2024
        "%d/%m/%Y",  # 15/01/2024
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def clean_linkedin_url(url: str) -> Optional[str]:
    """Normalize LinkedIn URL to consistent format."""
    if not url:
        return None
    match = re.search(r"linkedin\.com/in/([^/?\s]+)", url)
    if match:
        return f"https://www.linkedin.com/in/{match.group(1)}"
    return None


def get_column_value(row: dict, *names: str) -> str:
    """Get column value with case-insensitive fallback."""
    for name in names:
        if name in row:
            return row[name].strip()
        for key in row:
            if key.lower() == name.lower():
                return row[key].strip()
    return ""


def parse_connections_csv(
    path: Path,
    batch_id: str,
    user_name: Optional[str] = None,
) -> tuple[int, int, list[str]]:
    """
    Parse Connections.csv with batch tracking for diffing.

    Args:
        path: Path to Connections.csv
        batch_id: Import batch ID for tracking
        user_name: User's name to help identify message direction

    Returns:
        Tuple of (imported_count, updated_count, new_connection_ids)
    """
    imported = 0
    updated = 0
    new_ids = []

    with open(path, "r", encoding="utf-8-sig") as f:
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(f, dialect=dialect)

        with get_session() as session:
            for row in reader:
                first_name = get_column_value(row, "First Name", "FirstName")
                last_name = get_column_value(row, "Last Name", "LastName")
                name = f"{first_name} {last_name}".strip()

                if not name:
                    continue

                email = get_column_value(row, "Email Address", "Email", "EmailAddress")
                company = get_column_value(row, "Company", "Organization")
                position = get_column_value(row, "Position", "Title", "Job Title")
                url = get_column_value(row, "URL", "Profile URL", "LinkedIn URL")
                connected_on_str = get_column_value(row, "Connected On", "ConnectedOn")

                linkedin_url = clean_linkedin_url(url)
                connected_on = parse_linkedin_date(connected_on_str)

                # Check for existing
                existing = None
                if linkedin_url:
                    existing = session.exec(
                        select(Connection).where(Connection.linkedin_url == linkedin_url)
                    ).first()
                if not existing and email:
                    existing = session.exec(
                        select(Connection).where(Connection.email == email)
                    ).first()

                if existing:
                    # Update existing connection
                    existing.name = name
                    existing.email = email or existing.email
                    existing.current_role = position or existing.current_role
                    existing.current_company = company or existing.current_company
                    existing.connected_on = connected_on or existing.connected_on
                    existing.import_batch_id = batch_id
                    existing.updated_at = datetime.utcnow()
                    session.add(existing)
                    updated += 1
                else:
                    # Create new connection
                    connection = Connection(
                        name=name,
                        email=email or None,
                        linkedin_url=linkedin_url,
                        current_role=position or None,
                        current_company=company or None,
                        connection_source="linkedin_dump",
                        connected_on=connected_on,
                        import_batch_id=batch_id,
                        is_new_connection=True,
                    )
                    session.add(connection)
                    session.flush()  # Get the ID
                    new_ids.append(connection.id)
                    imported += 1

    return imported, updated, new_ids


def parse_messages_csv(path: Path, user_name: Optional[str] = None) -> dict[str, MessageStats]:
    """
    Parse Messages.csv and aggregate statistics per contact.

    Args:
        path: Path to Messages.csv
        user_name: User's name to determine message direction

    Returns:
        Dict mapping contact name -> MessageStats
    """
    conversations: dict[str, dict] = defaultdict(lambda: {
        "messages": [],
        "contact_names": set(),
    })

    with open(path, "r", encoding="utf-8-sig") as f:
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(f, dialect=dialect)

        for row in reader:
            conv_id = get_column_value(row, "CONVERSATION ID", "ConversationId", "Conversation ID")
            sender = get_column_value(row, "FROM", "Sender", "From")
            content = get_column_value(row, "CONTENT", "Message", "Content")
            date_str = get_column_value(row, "DATE", "Sent", "Date")

            if not conv_id:
                continue

            msg_date = parse_linkedin_date(date_str)

            conversations[conv_id]["messages"].append({
                "sender": sender,
                "content": content,
                "date": msg_date,
            })
            if sender:
                conversations[conv_id]["contact_names"].add(sender)

    # Aggregate per contact
    contact_stats: dict[str, MessageStats] = {}

    for conv_id, data in conversations.items():
        messages = sorted(data["messages"], key=lambda m: m["date"] or datetime.min)
        if not messages:
            continue

        # Identify the contact (not the user)
        contact_names = data["contact_names"]
        if user_name:
            contact_names = {n for n in contact_names if n.lower() != user_name.lower()}

        if not contact_names:
            continue

        contact_name = next(iter(contact_names))  # Take first contact name

        # Determine who initiated
        first_sender = messages[0].get("sender", "")
        is_user_initiated = user_name and first_sender.lower() == user_name.lower()

        stats = MessageStats(
            contact_name=contact_name,
            conversation_id=conv_id,
            message_count=len(messages),
            last_message_date=messages[-1].get("date"),
            first_sender="user" if is_user_initiated else "contact",
            last_messages=messages[-10:],  # Keep last 10 for summary
        )

        # Store by contact name (may have multiple conversations)
        if contact_name in contact_stats:
            existing = contact_stats[contact_name]
            existing.message_count += stats.message_count
            if stats.last_message_date and (
                not existing.last_message_date or stats.last_message_date > existing.last_message_date
            ):
                existing.last_message_date = stats.last_message_date
                existing.last_messages = stats.last_messages
        else:
            contact_stats[contact_name] = stats

    return contact_stats


def fuzzy_match_connection(
    contact_name: str,
    session,
) -> Optional[Connection]:
    """
    Find a Connection by fuzzy name matching.

    Args:
        contact_name: Name to search for
        session: Database session

    Returns:
        Best matching Connection or None
    """
    # First try exact match
    exact = session.exec(
        select(Connection).where(Connection.name == contact_name)
    ).first()
    if exact:
        return exact

    # Fuzzy match against all connections
    connections = session.exec(select(Connection)).all()
    best_match = None
    best_score = 0

    for conn in connections:
        score = fuzz.ratio(contact_name.lower(), conn.name.lower())
        if score > best_score and score >= 80:  # 80% threshold
            best_score = score
            best_match = conn

    return best_match


def update_connection_from_messages(
    contact_name: str,
    stats: MessageStats,
    session,
) -> bool:
    """
    Update a Connection with message statistics.

    Returns True if a matching connection was found and updated.
    """
    connection = fuzzy_match_connection(contact_name, session)
    if not connection:
        return False

    connection.message_count = stats.message_count
    connection.last_message_date = stats.last_message_date
    connection.initiated_by = stats.first_sender

    # Determine conversation status
    if stats.last_message_date:
        days_ago = (datetime.utcnow() - stats.last_message_date).days
        if days_ago <= settings.active_conversation_days:
            connection.conversation_status = "active"
        else:
            connection.conversation_status = "stale"
    else:
        connection.conversation_status = "never"

    session.add(connection)
    return True


def summarize_conversation_batch(
    stats_list: list[MessageStats],
    batch_size: int = 10,
) -> dict[str, str]:
    """
    Generate LLM summaries for conversations in batch.

    Args:
        stats_list: List of MessageStats with last_messages
        batch_size: How many to process at once

    Returns:
        Dict mapping contact_name -> summary
    """
    if not settings.openai_api_key:
        return {}

    client = OpenAI(api_key=settings.openai_api_key)
    summaries = {}

    for i in range(0, len(stats_list), batch_size):
        batch = stats_list[i:i + batch_size]

        # Build batch prompt
        conversations_text = []
        for stats in batch:
            if not stats.last_messages:
                continue
            msgs = "\n".join([
                f"  {m.get('sender', 'Unknown')}: {m.get('content', '')[:200]}"
                for m in stats.last_messages
            ])
            conversations_text.append(f"Contact: {stats.contact_name}\n{msgs}")

        if not conversations_text:
            continue

        prompt = f"""Summarize each of these LinkedIn conversations in 1-2 sentences.
Focus on: relationship context, topics discussed, any action items or follow-ups mentioned.

{chr(10).join(conversations_text)}

Return JSON format:
{{"summaries": [{{"contact": "Name", "summary": "Brief summary"}}]}}"""

        try:
            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            import json
            data = json.loads(response.choices[0].message.content)
            for item in data.get("summaries", []):
                summaries[item["contact"]] = item["summary"]

        except Exception as e:
            print(f"Error summarizing batch: {e}")

    return summaries


def diff_connections(batch_id: str) -> list[str]:
    """
    Find new connections from an import batch.

    Args:
        batch_id: The import batch ID to check

    Returns:
        List of connection IDs that are new in this batch
    """
    with get_session() as session:
        new_connections = session.exec(
            select(Connection)
            .where(Connection.import_batch_id == batch_id)
            .where(Connection.is_new_connection == True)
        ).all()
        return [c.id for c in new_connections]


def import_linkedin_dump(
    zip_path: Path,
    user_name: Optional[str] = None,
    summarize_conversations: bool = True,
) -> DumpImportResult:
    """
    Full import of LinkedIn data dump.

    Args:
        zip_path: Path to LinkedIn export ZIP
        user_name: User's name for message direction detection
        summarize_conversations: Whether to generate LLM summaries

    Returns:
        DumpImportResult with import statistics
    """
    # Create import batch
    batch_id = None
    file_hash = compute_file_hash(zip_path)

    with get_session() as session:
        batch = ImportBatch(
            source_type="linkedin_dump",
            file_hash=file_hash,
        )
        session.add(batch)
        session.flush()
        batch_id = batch.id

    result = DumpImportResult(batch_id=batch_id)

    try:
        # Extract ZIP
        dump = extract_linkedin_dump(zip_path)

        # Parse connections
        if dump.connections_path:
            imported, updated, new_ids = parse_connections_csv(
                dump.connections_path, batch_id, user_name
            )
            result.connections_imported = imported
            result.connections_updated = updated
            result.new_connection_ids = new_ids

        # Parse messages
        if dump.messages_path:
            message_stats = parse_messages_csv(dump.messages_path, user_name)
            result.messages_processed = len(message_stats)

            # Update connections with message data
            with get_session() as session:
                for contact_name, stats in message_stats.items():
                    update_connection_from_messages(contact_name, stats, session)

            # Generate conversation summaries
            if summarize_conversations and message_stats:
                stats_with_messages = [
                    s for s in message_stats.values() if s.last_messages
                ]
                summaries = summarize_conversation_batch(stats_with_messages)

                with get_session() as session:
                    for contact_name, summary in summaries.items():
                        conn = fuzzy_match_connection(contact_name, session)
                        if conn:
                            conn.conversation_summary = summary
                            session.add(conn)
                            result.conversations_summarized += 1

        # Update batch with results
        with get_session() as session:
            batch = session.get(ImportBatch, batch_id)
            if batch:
                batch.imported_count = result.connections_imported
                batch.updated_count = result.connections_updated
                batch.new_connection_ids = result.new_connection_ids
                batch.completed_at = datetime.utcnow()
                session.add(batch)

    except Exception as e:
        result.errors.append(str(e))

    return result
