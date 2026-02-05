"""LinkedIn CSV import module for Reconnect."""

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import select

from src.database.engine import get_session
from src.database.models import Connection


@dataclass
class ImportResult:
    """Result of a CSV import operation."""

    total_rows: int = 0
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def clean_linkedin_url(url: str) -> Optional[str]:
    """Normalize LinkedIn URL to consistent format."""
    if not url:
        return None

    # Extract the profile path
    match = re.search(r"linkedin\.com/in/([^/?\s]+)", url)
    if match:
        return f"https://www.linkedin.com/in/{match.group(1)}"
    return None


def parse_linkedin_date(date_str: str) -> Optional[datetime]:
    """Parse LinkedIn's date format."""
    if not date_str:
        return None

    formats = [
        "%d %b %Y",  # 15 Jan 2024
        "%b %d, %Y",  # Jan 15, 2024
        "%Y-%m-%d",  # 2024-01-15
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def get_column_value(row: dict, *names: str) -> str:
    """Get column value with case-insensitive fallback."""
    for name in names:
        if name in row:
            return row[name].strip()
        # Case-insensitive fallback
        for key in row:
            if key.lower() == name.lower():
                return row[key].strip()
    return ""


def import_linkedin_csv(file_path: Path) -> ImportResult:
    """
    Import contacts from LinkedIn connections export CSV.

    Expected columns (LinkedIn export format):
    - First Name, Last Name
    - Email Address
    - Company
    - Position
    - Connected On
    - URL (LinkedIn profile)
    """
    result = ImportResult()

    with open(file_path, "r", encoding="utf-8-sig") as f:
        # Detect delimiter (LinkedIn sometimes uses different ones)
        sample = f.read(2048)
        f.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel  # Default to comma-separated

        reader = csv.DictReader(f, dialect=dialect)

        with get_session() as session:
            for i, row in enumerate(reader, 1):
                result.total_rows += 1

                try:
                    # Extract fields
                    first_name = get_column_value(row, "First Name", "FirstName")
                    last_name = get_column_value(row, "Last Name", "LastName")
                    name = f"{first_name} {last_name}".strip()

                    if not name:
                        result.skipped += 1
                        result.errors.append(f"Row {i}: Missing name")
                        continue

                    email = get_column_value(row, "Email Address", "Email", "EmailAddress")
                    company = get_column_value(row, "Company", "Organization")
                    position = get_column_value(row, "Position", "Title", "Job Title")
                    url = get_column_value(row, "URL", "Profile URL", "LinkedIn URL")

                    linkedin_url = clean_linkedin_url(url)

                    # Check for existing connection
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
                        # Update existing
                        existing.name = name
                        existing.email = email or existing.email
                        existing.current_role = position or existing.current_role
                        existing.current_company = company or existing.current_company
                        existing.updated_at = datetime.utcnow()
                        session.add(existing)
                        result.updated += 1
                    else:
                        # Create new
                        connection = Connection(
                            name=name,
                            email=email or None,
                            linkedin_url=linkedin_url,
                            current_role=position or None,
                            current_company=company or None,
                            connection_source="linkedin_export",
                        )
                        session.add(connection)
                        result.imported += 1

                except Exception as e:
                    result.skipped += 1
                    result.errors.append(f"Row {i}: {str(e)}")

            session.commit()

    return result
