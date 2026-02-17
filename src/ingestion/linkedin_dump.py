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
from src.database.models import Connection, EngagementSignal, ImportBatch, UserContent


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
    shares_path: Optional[Path] = None
    endorsements_received_path: Optional[Path] = None
    endorsements_given_path: Optional[Path] = None
    recommendations_received_path: Optional[Path] = None
    recommendations_given_path: Optional[Path] = None
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
    engagement_signals_created: int = 0
    user_content_created: int = 0
    endorsements_processed: int = 0
    recommendations_processed: int = 0
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
        elif "share" in name_lower:
            result.shares_path = csv_file
        elif "endorsement" in name_lower and "received" in name_lower:
            result.endorsements_received_path = csv_file
        elif "endorsement" in name_lower and "given" in name_lower:
            result.endorsements_given_path = csv_file
        elif "recommendation" in name_lower and "received" in name_lower:
            result.recommendations_received_path = csv_file
        elif "recommendation" in name_lower and "given" in name_lower:
            result.recommendations_given_path = csv_file

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
            val = row[name]
            return val.strip() if val else ""
        for key in row:
            if key and key.lower() == name.lower():
                val = row[key]
                return val.strip() if val else ""
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
        # LinkedIn CSVs often have a "Notes:" section at the top
        # Skip lines until we find the actual header row
        lines = f.readlines()

    # Find the header row (starts with "First Name")
    header_idx = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("First Name"):
            header_idx = i
            break

    # Parse from the header row onwards
    import io
    csv_content = "".join(lines[header_idx:])
    f = io.StringIO(csv_content)

    try:
        dialect = csv.Sniffer().sniff(csv_content[:2048], delimiters=",;\t")
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
            contact_names = {n for n in contact_names if n and n.lower() != user_name.lower()}
        else:
            contact_names = {n for n in contact_names if n}  # Filter out None values

        if not contact_names:
            continue

        contact_name = next(iter(contact_names))  # Take first contact name

        # Determine who initiated
        first_sender = messages[0].get("sender") or ""
        is_user_initiated = user_name and first_sender and first_sender.lower() == user_name.lower()

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
    if not contact_name:
        return None

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
        if not conn.name:
            continue
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


def parse_reactions_csv(path: Path, user_name: Optional[str] = None) -> list[EngagementSignal]:
    """
    Parse Reactions.csv to extract engagement signals.

    LinkedIn reactions CSV typically contains:
    - Type (reaction type like LIKE, CELEBRATE, etc.)
    - Date
    - Link (to the post)
    - The post author may be extractable from the link or content

    Args:
        path: Path to Reactions.csv
        user_name: User's name (the reactor)

    Returns:
        List of EngagementSignal objects
    """
    signals = []

    if not path or not path.exists():
        return signals

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel

            reader = csv.DictReader(f, dialect=dialect)

            for row in reader:
                reaction_type = get_column_value(row, "Type", "Reaction Type", "ReactionType")
                date_str = get_column_value(row, "Date", "Reacted On")
                link = get_column_value(row, "Link", "Post Link", "URL")

                # Try to extract author name from various possible columns
                author = get_column_value(row, "Author", "Post Author", "Name", "Creator")

                # If no explicit author column, try to extract from link
                # LinkedIn post URLs sometimes contain the author's profile slug
                if not author and link:
                    match = re.search(r"linkedin\.com/(?:posts|pulse|feed/update)/([^/?\s]+)", link)
                    if match:
                        # This might be a post ID or author slug
                        author = match.group(1).replace("-", " ").title()

                if not author:
                    author = "Unknown"

                # Determine signal strength based on reaction type
                strength = 1
                reaction_lower = reaction_type.lower() if reaction_type else ""
                if "celebrate" in reaction_lower or "love" in reaction_lower:
                    strength = 3
                elif "insightful" in reaction_lower or "curious" in reaction_lower:
                    strength = 2

                signal = EngagementSignal(
                    connection_name=author,
                    signal_type="reaction",
                    signal_strength=strength,
                    content_snippet=f"{reaction_type} on post" if reaction_type else None,
                    signal_date=parse_linkedin_date(date_str),
                )
                signals.append(signal)

    except Exception as e:
        print(f"Error parsing reactions: {e}")

    return signals


def parse_comments_csv(path: Path, user_name: Optional[str] = None) -> list[EngagementSignal]:
    """
    Parse Comments.csv to extract engagement signals.

    Args:
        path: Path to Comments.csv
        user_name: User's name (the commenter)

    Returns:
        List of EngagementSignal objects
    """
    signals = []

    if not path or not path.exists():
        return signals

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel

            reader = csv.DictReader(f, dialect=dialect)

            for row in reader:
                date_str = get_column_value(row, "Date", "Commented On")
                link = get_column_value(row, "Link", "Post Link", "URL")
                content = get_column_value(row, "Message", "Comment", "Content")

                # Try to extract author name
                author = get_column_value(row, "Author", "Post Author", "Name", "Creator")

                if not author and link:
                    match = re.search(r"linkedin\.com/(?:posts|pulse|feed/update)/([^/?\s]+)", link)
                    if match:
                        author = match.group(1).replace("-", " ").title()

                if not author:
                    author = "Unknown"

                # Comments are higher engagement than reactions
                signal = EngagementSignal(
                    connection_name=author,
                    signal_type="comment",
                    signal_strength=3,  # Comments show more engagement
                    content_snippet=content[:200] if content else None,
                    signal_date=parse_linkedin_date(date_str),
                )
                signals.append(signal)

    except Exception as e:
        print(f"Error parsing comments: {e}")

    return signals


def parse_endorsements_csv(
    path: Path,
    direction: str,  # "given" or "received"
) -> list[EngagementSignal]:
    """
    Parse Endorsements Given/Received CSV.

    Args:
        path: Path to endorsements CSV
        direction: "given" or "received"

    Returns:
        List of EngagementSignal objects
    """
    signals = []

    if not path or not path.exists():
        return signals

    signal_type = f"endorsement_{direction}"

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel

            reader = csv.DictReader(f, dialect=dialect)

            for row in reader:
                # The name field depends on direction
                if direction == "given":
                    name = get_column_value(row, "Endorsee First Name", "First Name")
                    last_name = get_column_value(row, "Endorsee Last Name", "Last Name")
                else:
                    name = get_column_value(row, "Endorser First Name", "First Name")
                    last_name = get_column_value(row, "Endorser Last Name", "Last Name")

                full_name = f"{name} {last_name}".strip()
                if not full_name:
                    continue

                skill = get_column_value(row, "Skill Name", "Skill", "Endorsed Skill")
                date_str = get_column_value(row, "Date", "Endorsement Date", "Endorsed On")

                signal = EngagementSignal(
                    connection_name=full_name,
                    signal_type=signal_type,
                    signal_strength=2,  # Endorsements are moderate signals
                    content_snippet=f"Skill: {skill}" if skill else None,
                    signal_date=parse_linkedin_date(date_str),
                )
                signals.append(signal)

    except Exception as e:
        print(f"Error parsing endorsements: {e}")

    return signals


def parse_recommendations_csv(
    path: Path,
    direction: str,  # "given" or "received"
) -> list[EngagementSignal]:
    """
    Parse Recommendations Given/Received CSV.

    Args:
        path: Path to recommendations CSV
        direction: "given" or "received"

    Returns:
        List of EngagementSignal objects
    """
    signals = []

    if not path or not path.exists():
        return signals

    signal_type = f"recommendation_{direction}"

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel

            reader = csv.DictReader(f, dialect=dialect)

            for row in reader:
                # The name field depends on direction
                if direction == "given":
                    name = get_column_value(row, "Recommendee First Name", "First Name")
                    last_name = get_column_value(row, "Recommendee Last Name", "Last Name")
                else:
                    name = get_column_value(row, "Recommender First Name", "First Name")
                    last_name = get_column_value(row, "Recommender Last Name", "Last Name")

                full_name = f"{name} {last_name}".strip()
                if not full_name:
                    continue

                text = get_column_value(row, "Recommendation Text", "Text", "Content")
                date_str = get_column_value(row, "Date", "Recommendation Date", "Created On")

                signal = EngagementSignal(
                    connection_name=full_name,
                    signal_type=signal_type,
                    signal_strength=5,  # Recommendations are strong signals
                    content_snippet=text[:200] if text else None,
                    signal_date=parse_linkedin_date(date_str),
                )
                signals.append(signal)

    except Exception as e:
        print(f"Error parsing recommendations: {e}")

    return signals


def parse_shares_csv(path: Path) -> list[UserContent]:
    """
    Parse Shares.csv to extract user's own posts.

    Args:
        path: Path to Shares.csv

    Returns:
        List of UserContent objects (limited to most recent 50)
    """
    contents = []

    if not path or not path.exists():
        return contents

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel

            reader = csv.DictReader(f, dialect=dialect)

            for row in reader:
                date_str = get_column_value(row, "Date", "Shared On", "Posted On")
                text = get_column_value(row, "ShareCommentary", "Commentary", "Text", "Content")
                link = get_column_value(row, "ShareLink", "Link", "URL")

                # Determine content type
                content_type = "share"
                if not link or "linkedin.com" not in link:
                    content_type = "post"

                content = UserContent(
                    content_type=content_type,
                    content_text=text if text else None,
                    posted_at=parse_linkedin_date(date_str),
                )
                contents.append(content)

    except Exception as e:
        print(f"Error parsing shares: {e}")

    # Sort by date and limit to most recent 50
    contents.sort(key=lambda c: c.posted_at or datetime.min, reverse=True)
    return contents[:50]


def parse_profile_csv(path: Path) -> dict:
    """
    Parse Profile.csv to extract headline and about section.

    Args:
        path: Path to Profile.csv

    Returns:
        Dict with headline and about_summary
    """
    result = {"headline": None, "about_summary": None}

    if not path or not path.exists():
        return result

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel

            reader = csv.DictReader(f, dialect=dialect)

            for row in reader:
                headline = get_column_value(row, "Headline", "Professional Headline")
                about = get_column_value(row, "Summary", "About", "Bio")

                if headline:
                    result["headline"] = headline
                if about:
                    result["about_summary"] = about
                break  # Profile.csv typically has one row

    except Exception as e:
        print(f"Error parsing profile: {e}")

    return result


def save_engagement_signals(signals: list[EngagementSignal]) -> int:
    """
    Save engagement signals to database and link to connections.

    Args:
        signals: List of EngagementSignal objects

    Returns:
        Number of signals saved
    """
    if not signals:
        return 0

    saved = 0

    with get_session() as session:
        for signal in signals:
            # Try to link to a connection
            connection = fuzzy_match_connection(signal.connection_name, session)
            if connection:
                signal.connection_id = connection.id

            session.add(signal)
            saved += 1

    return saved


def aggregate_engagement_signals() -> dict[str, dict]:
    """
    Aggregate engagement signals per connection to compute scores.

    Returns:
        Dict mapping connection_id -> engagement metrics
    """
    aggregated: dict[str, dict] = defaultdict(lambda: {
        "total_signals": 0,
        "weighted_score": 0,
        "last_date": None,
        "user_to_contact": 0,
        "contact_to_user": 0,
        "endorsement_count": 0,
        "has_recommendation": False,
    })

    with get_session() as session:
        signals = session.exec(select(EngagementSignal)).all()

        for signal in signals:
            if not signal.connection_id:
                continue

            agg = aggregated[signal.connection_id]
            agg["total_signals"] += 1
            agg["weighted_score"] += signal.signal_strength

            # Track most recent engagement
            if signal.signal_date:
                if not agg["last_date"] or signal.signal_date > agg["last_date"]:
                    agg["last_date"] = signal.signal_date

            # Track direction
            if signal.signal_type in ("reaction", "comment", "endorsement_given", "recommendation_given"):
                agg["user_to_contact"] += 1
            elif signal.signal_type in ("endorsement_received", "recommendation_received"):
                agg["contact_to_user"] += 1

            # Track endorsements and recommendations
            if "endorsement" in signal.signal_type:
                agg["endorsement_count"] += 1
            if "recommendation" in signal.signal_type:
                agg["has_recommendation"] = True

    return dict(aggregated)


def update_connection_engagement_scores():
    """
    Update connections with aggregated engagement scores.
    """
    aggregated = aggregate_engagement_signals()

    if not aggregated:
        return

    with get_session() as session:
        for connection_id, metrics in aggregated.items():
            connection = session.get(Connection, connection_id)
            if not connection:
                continue

            # Compute engagement score (0-100)
            # Formula: weighted_score normalized, with diminishing returns
            raw_score = metrics["weighted_score"]
            # Cap at ~50 weighted points for 100 score
            engagement_score = min(100, (raw_score / 50) * 100)

            connection.engagement_score = round(engagement_score, 1)
            connection.last_engagement_date = metrics["last_date"]

            # Determine direction
            user_to = metrics["user_to_contact"]
            contact_to = metrics["contact_to_user"]
            if user_to > 0 and contact_to > 0:
                connection.engagement_direction = "mutual"
            elif user_to > 0:
                connection.engagement_direction = "user_to_contact"
            elif contact_to > 0:
                connection.engagement_direction = "contact_to_user"

            connection.endorsement_count = metrics["endorsement_count"]
            connection.has_recommendation = metrics["has_recommendation"]

            session.add(connection)


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

        # Parse engagement signals (reactions, comments)
        all_signals: list[EngagementSignal] = []

        if dump.reactions_path:
            reactions = parse_reactions_csv(dump.reactions_path, user_name)
            all_signals.extend(reactions)

        if dump.comments_path:
            comments = parse_comments_csv(dump.comments_path, user_name)
            all_signals.extend(comments)

        # Parse endorsements
        if dump.endorsements_given_path:
            given = parse_endorsements_csv(dump.endorsements_given_path, "given")
            all_signals.extend(given)
            result.endorsements_processed += len(given)

        if dump.endorsements_received_path:
            received = parse_endorsements_csv(dump.endorsements_received_path, "received")
            all_signals.extend(received)
            result.endorsements_processed += len(received)

        # Parse recommendations
        if dump.recommendations_given_path:
            given = parse_recommendations_csv(dump.recommendations_given_path, "given")
            all_signals.extend(given)
            result.recommendations_processed += len(given)

        if dump.recommendations_received_path:
            received = parse_recommendations_csv(dump.recommendations_received_path, "received")
            all_signals.extend(received)
            result.recommendations_processed += len(received)

        # Save all engagement signals
        if all_signals:
            result.engagement_signals_created = save_engagement_signals(all_signals)
            # Aggregate and update connection scores
            update_connection_engagement_scores()

        # Parse user's own posts/shares
        if dump.shares_path:
            shares = parse_shares_csv(dump.shares_path)
            if shares:
                with get_session() as session:
                    for content in shares:
                        session.add(content)
                    result.user_content_created = len(shares)

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


def find_latest_linkedin_export(
    search_folder: Optional[Path] = None,
    pattern: Optional[str] = None,
) -> Optional[Path]:
    """
    Find the most recent LinkedIn export in a folder.

    Looks for both ZIP files and extracted folders matching the pattern.
    Returns the most recently modified one.

    Args:
        search_folder: Folder to search in (default: settings.linkedin_data_folder)
        pattern: Glob pattern (default: settings.linkedin_export_pattern)

    Returns:
        Path to the latest LinkedIn export (ZIP preferred), or None
    """
    from src.config import settings

    folder = Path(search_folder or settings.linkedin_data_folder).expanduser()
    pat = pattern or settings.linkedin_export_pattern

    if not folder.exists():
        return None

    # Find all matching files/folders
    matches = []

    # Look for ZIPs first (preferred)
    for p in folder.glob(f"{pat}.zip"):
        if p.is_file():
            matches.append(p)

    # Also look for extracted folders
    for p in folder.glob(pat):
        if p.is_dir() and (p / "Connections.csv").exists():
            matches.append(p)

    if not matches:
        return None

    # Sort by modification time, most recent first
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    return matches[0]


def is_already_imported(file_path: Path) -> bool:
    """
    Check if a LinkedIn export has already been imported.

    Args:
        file_path: Path to ZIP or folder

    Returns:
        True if this exact file has been imported before
    """
    # For folders, check if Connections.csv exists and hash that
    if file_path.is_dir():
        connections_csv = file_path / "Connections.csv"
        if not connections_csv.exists():
            return False
        file_hash = compute_file_hash(connections_csv)
    else:
        file_hash = compute_file_hash(file_path)

    with get_session() as session:
        existing = session.exec(
            select(ImportBatch).where(ImportBatch.file_hash == file_hash)
        ).first()
        return existing is not None


def auto_import_linkedin_dump(
    search_folder: Optional[Path] = None,
    user_name: Optional[str] = None,
    summarize_conversations: bool = False,
) -> Optional[DumpImportResult]:
    """
    Find and import the latest LinkedIn export if not already imported.

    This is designed to be called by the scheduled pipeline to automatically
    pick up new LinkedIn exports from the Downloads folder.

    Args:
        search_folder: Folder to search (default: settings.linkedin_data_folder)
        user_name: User's name for message direction detection
        summarize_conversations: Whether to generate LLM summaries

    Returns:
        DumpImportResult if a new export was imported, None otherwise
    """
    latest = find_latest_linkedin_export(search_folder)

    if not latest:
        return None

    if is_already_imported(latest):
        return None

    # Import the new export
    if latest.is_dir():
        return import_linkedin_folder(latest, user_name, summarize_conversations)
    else:
        return import_linkedin_dump(latest, user_name, summarize_conversations)


def import_linkedin_folder(
    folder_path: Path,
    user_name: Optional[str] = None,
    summarize_conversations: bool = False,
) -> DumpImportResult:
    """
    Import from an already-extracted LinkedIn folder.

    Args:
        folder_path: Path to extracted LinkedIn folder
        user_name: User's name for message direction detection
        summarize_conversations: Whether to generate LLM summaries

    Returns:
        DumpImportResult with import statistics
    """
    # Create import batch using Connections.csv hash
    connections_csv = folder_path / "Connections.csv"
    if not connections_csv.exists():
        result = DumpImportResult(batch_id="")
        result.errors.append(f"No Connections.csv found in {folder_path}")
        return result

    batch_id = None
    file_hash = compute_file_hash(connections_csv)

    with get_session() as session:
        batch = ImportBatch(
            source_type="linkedin_folder",
            file_hash=file_hash,
        )
        session.add(batch)
        session.flush()
        batch_id = batch.id

    result = DumpImportResult(batch_id=batch_id)

    try:
        # Create ExtractedDump from folder
        dump = ExtractedDump(extract_dir=folder_path)

        # Map expected files
        file_mappings = {
            "connections_path": "Connections.csv",
            "messages_path": "Messages.csv",
            "profile_path": "Profile.csv",
            "positions_path": "Positions.csv",
            "skills_path": "Skills.csv",
            "reactions_path": "Reactions.csv",
            "comments_path": "Comments.csv",
            "shares_path": "Shares.csv",
            "endorsements_received_path": "Endorsements_Received.csv",
            "endorsements_given_path": "Endorsements_Given.csv",
            "recommendations_received_path": "Recommendations_Received.csv",
            "recommendations_given_path": "Recommendations_Given.csv",
        }

        for attr, filename in file_mappings.items():
            filepath = folder_path / filename
            if filepath.exists():
                setattr(dump, attr, filepath)

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

            with get_session() as session:
                for contact_name, stats in message_stats.items():
                    update_connection_from_messages(contact_name, stats, session)

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

        # Parse engagement signals
        all_signals: list[EngagementSignal] = []

        if dump.reactions_path:
            reactions = parse_reactions_csv(dump.reactions_path, user_name)
            all_signals.extend(reactions)

        if dump.comments_path:
            comments = parse_comments_csv(dump.comments_path, user_name)
            all_signals.extend(comments)

        if dump.endorsements_given_path:
            given = parse_endorsements_csv(dump.endorsements_given_path, "given")
            all_signals.extend(given)
            result.endorsements_processed += len(given)

        if dump.endorsements_received_path:
            received = parse_endorsements_csv(dump.endorsements_received_path, "received")
            all_signals.extend(received)
            result.endorsements_processed += len(received)

        if dump.recommendations_given_path:
            given = parse_recommendations_csv(dump.recommendations_given_path, "given")
            all_signals.extend(given)
            result.recommendations_processed += len(given)

        if dump.recommendations_received_path:
            received = parse_recommendations_csv(dump.recommendations_received_path, "received")
            all_signals.extend(received)
            result.recommendations_processed += len(received)

        if all_signals:
            result.engagement_signals_created = save_engagement_signals(all_signals)
            update_connection_engagement_scores()

        if dump.shares_path:
            shares = parse_shares_csv(dump.shares_path)
            if shares:
                with get_session() as session:
                    for content in shares:
                        session.add(content)
                    result.user_content_created = len(shares)

        # Update batch
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
