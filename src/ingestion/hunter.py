"""Hunter.io integration for email finding and enrichment."""

import re
from datetime import datetime
from typing import Optional

import requests

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection


HUNTER_API_BASE = "https://api.hunter.io/v2"


def get_hunter_client() -> Optional[str]:
    """Get Hunter API key if configured."""
    if not settings.hunter_api_key:
        return None
    return settings.hunter_api_key


def extract_domain_from_company(company: str) -> Optional[str]:
    """
    Attempt to derive a domain from a company name.

    Args:
        company: Company name (e.g., "Google", "Acme Corp")

    Returns:
        Likely domain (e.g., "google.com") or None
    """
    if not company:
        return None

    # Clean up company name
    clean = company.lower().strip()

    # Remove common suffixes
    for suffix in [", inc.", ", inc", " inc.", " inc", ", llc", " llc", ", ltd", " ltd", " corp.", " corp", " co.", " co"]:
        clean = clean.replace(suffix, "")

    # Remove special characters and spaces
    clean = re.sub(r"[^a-z0-9]", "", clean)

    if clean:
        return f"{clean}.com"

    return None


def find_email(
    first_name: str,
    last_name: str,
    domain: Optional[str] = None,
    company: Optional[str] = None,
) -> Optional[dict]:
    """
    Find email address using Hunter.io Email Finder API.

    Args:
        first_name: Person's first name
        last_name: Person's last name
        domain: Company domain (e.g., "google.com")
        company: Company name (used to derive domain if not provided)

    Returns:
        Dict with email data, or None if not found

    Response fields:
        - email: Found email address
        - score: Confidence score (0-100)
        - position: Job title if available
        - company: Company name
        - sources: List of sources where email was found
        - verification: Verification status if available
    """
    api_key = get_hunter_client()

    if not api_key:
        # Return mock data for development
        return _get_mock_email_data(first_name, last_name, domain or company)

    # Determine domain
    search_domain = domain
    if not search_domain and company:
        search_domain = extract_domain_from_company(company)

    if not search_domain:
        return None

    try:
        response = requests.get(
            f"{HUNTER_API_BASE}/email-finder",
            params={
                "api_key": api_key,
                "domain": search_domain,
                "first_name": first_name,
                "last_name": last_name,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("data", {}).get("email"):
            result = data["data"]
            result["_fetched_at"] = datetime.utcnow().isoformat()
            result["_source"] = "hunter"
            return result

        return None

    except requests.exceptions.RequestException as e:
        print(f"Hunter API error: {e}")
        return None


def enrich_from_email(email: str) -> Optional[dict]:
    """
    Get enrichment data for an email using Hunter.io Combined Enrichment API.

    Args:
        email: Professional email address

    Returns:
        Dict with person and company data, or None if not found

    Response includes:
        - person: Name, location, social profiles, employment details
        - company: Name, domain, industry, size, tech stack
    """
    api_key = get_hunter_client()

    if not api_key:
        return _get_mock_enrichment_data(email)

    try:
        response = requests.get(
            f"{HUNTER_API_BASE}/combined/find",
            params={
                "api_key": api_key,
                "email": email,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("data"):
            result = data["data"]
            result["_fetched_at"] = datetime.utcnow().isoformat()
            result["_source"] = "hunter"
            return result

        return None

    except requests.exceptions.RequestException as e:
        print(f"Hunter enrichment error: {e}")
        return None


def find_email_for_connection(connection_id: str) -> bool:
    """
    Find and store email for a connection using Hunter.io.

    Args:
        connection_id: UUID of the connection

    Returns:
        True if email was found and stored, False otherwise
    """
    with get_session() as session:
        connection = session.get(Connection, connection_id)
        if not connection:
            return False

        # Skip if already has email
        if connection.email:
            return True

        # Need name and company to search
        if not connection.name:
            return False

        # Parse first/last name
        name_parts = connection.name.strip().split()
        if len(name_parts) < 2:
            return False

        first_name = name_parts[0]
        last_name = " ".join(name_parts[1:])

        # Get company from current_company or company field
        company = connection.current_company or connection.company
        if not company:
            return False

        try:
            result = find_email(
                first_name=first_name,
                last_name=last_name,
                company=company,
            )

            if not result or not result.get("email"):
                return False

            # Store the email
            connection.email = result["email"]

            # Store Hunter data in raw_enrichment (merge with existing)
            existing = connection.raw_enrichment or {}
            existing["hunter_email"] = result
            connection.raw_enrichment = existing

            connection.updated_at = datetime.utcnow()
            session.add(connection)

            return True

        except Exception as e:
            print(f"Error finding email for {connection_id}: {e}")
            return False


def find_emails_batch(
    connection_ids: list[str],
    progress_callback=None,
) -> dict:
    """
    Find emails for multiple connections.

    Args:
        connection_ids: List of connection UUIDs
        progress_callback: Optional callback(current, total) for progress

    Returns:
        Dict with counts: {"found": N, "skipped": N, "failed": N, "errors": [...]}
    """
    results = {"found": 0, "skipped": 0, "failed": 0, "errors": []}
    total = len(connection_ids)

    for i, conn_id in enumerate(connection_ids):
        try:
            with get_session() as session:
                connection = session.get(Connection, conn_id)
                if connection and connection.email:
                    results["skipped"] += 1
                    continue

            if find_email_for_connection(conn_id):
                results["found"] += 1
            else:
                results["failed"] += 1

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{conn_id}: {str(e)[:50]}")

        if progress_callback:
            progress_callback(i + 1, total)

    return results


def get_contacts_missing_email(limit: int = 100) -> list[Connection]:
    """
    Get tier-1 contacts that don't have an email address.

    Args:
        limit: Max contacts to return

    Returns:
        List of Connection objects missing email
    """
    from sqlmodel import select

    with get_session() as session:
        stmt = (
            select(Connection)
            .where(Connection.pre_score_tier == 1)
            .where(
                (Connection.email == None) | (Connection.email == "")  # noqa: E711
            )
            .where(Connection.current_company != None)  # noqa: E711
            .order_by(Connection.pre_score.desc())
            .limit(limit)
        )
        connections = session.exec(stmt).all()

        # Detach from session
        result = []
        for conn in connections:
            _ = conn.id, conn.name, conn.company
            result.append(conn)

        return result


def _get_mock_email_data(first_name: str, last_name: str, company: str) -> dict:
    """Return mock email finder data for development."""
    domain = extract_domain_from_company(company) if company else "example.com"
    email = f"{first_name.lower()}.{last_name.lower()}@{domain}"

    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "score": 85,
        "domain": domain,
        "position": "Product Manager",
        "company": company or "Example Corp",
        "twitter": None,
        "linkedin_url": None,
        "phone_number": None,
        "sources": [
            {
                "domain": domain,
                "uri": f"https://{domain}/team",
                "extracted_on": "2024-01-15",
                "last_seen_on": "2024-06-01",
                "still_on_page": True,
            }
        ],
        "verification": {
            "date": "2024-06-01",
            "status": "valid",
        },
        "_fetched_at": datetime.utcnow().isoformat(),
        "_source": "hunter_mock",
    }


def _get_mock_enrichment_data(email: str) -> dict:
    """Return mock enrichment data for development."""
    return {
        "person": {
            "email": email,
            "firstName": "John",
            "lastName": "Doe",
            "fullName": "John Doe",
            "location": "San Francisco, CA",
            "timeZone": "America/Los_Angeles",
            "title": "Senior Product Manager",
            "seniority": "manager",
            "role": "product",
            "companyDomain": "example.com",
            "twitter": "@johndoe",
            "github": "johndoe",
            "linkedin": "in/johndoe",
        },
        "company": {
            "name": "Example Corp",
            "legalName": "Example Corporation",
            "domain": "example.com",
            "domainAliases": ["example.io"],
            "description": "A technology company building innovative products.",
            "sector": "Technology",
            "industry": "Software",
            "employeesRange": "51-200",
            "foundedYear": 2015,
            "location": "San Francisco, CA",
            "linkedin": "company/example-corp",
            "twitter": "@examplecorp",
        },
        "_fetched_at": datetime.utcnow().isoformat(),
        "_source": "hunter_mock",
    }
