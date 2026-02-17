"""RapidAPI LinkedIn enrichment integration."""

from datetime import datetime
from typing import Optional

import requests

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection


RAPIDAPI_HOST = "fresh-linkedin-profile-data.p.rapidapi.com"
RAPIDAPI_BASE_URL = f"https://{RAPIDAPI_HOST}"


def fetch_linkedin_profile(linkedin_url: str) -> Optional[dict]:
    """
    Fetch LinkedIn profile data using RapidAPI.

    Args:
        linkedin_url: LinkedIn profile URL

    Returns:
        Profile data dict, or None if fetch fails
    """
    if not settings.rapidapi_key:
        # Return mock data for development
        return _get_mock_profile_data()

    try:
        headers = {
            "x-rapidapi-key": settings.rapidapi_key,
            "x-rapidapi-host": RAPIDAPI_HOST,
        }

        params = {
            "linkedin_url": linkedin_url,
            "include_skills": "true",
            "include_certifications": "false",
            "include_publications": "false",
            "include_honors": "false",
            "include_volunteers": "false",
            "include_projects": "false",
            "include_patents": "false",
            "include_courses": "false",
            "include_organizations": "false",
            "include_profile_status": "false",
            "include_company_public_url": "false",
        }

        response = requests.get(
            f"{RAPIDAPI_BASE_URL}/enrich-lead",
            headers=headers,
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            print(f"RapidAPI error: {response.status_code} - {response.text[:200]}")
            return None

        profile_data = response.json()

        # Add metadata
        profile_data["_fetched_at"] = datetime.utcnow().isoformat()
        profile_data["_source"] = "rapidapi"

        return profile_data

    except Exception as e:
        print(f"RapidAPI fetch error: {e}")
        return None


def extract_activity_log(profile_data: dict) -> list[dict]:
    """
    Extract and normalize posts/updates into activity_log format.

    Args:
        profile_data: Full RapidAPI profile response

    Returns:
        List of activity items in normalized format
    """
    activity_log = []

    # RapidAPI may have different field names - adapt as needed
    for post in profile_data.get("posts", []):
        activity_log.append({
            "type": "post",
            "content": post.get("text", ""),
            "url": post.get("url", ""),
            "post_type": "Post",
            "source": "rapidapi",
        })

    return activity_log


def update_connection_from_profile(connection_id: str) -> bool:
    """
    Fetch and store LinkedIn profile data for a connection.

    Args:
        connection_id: UUID of the connection to update

    Returns:
        True if successful, False otherwise
    """
    with get_session() as session:
        connection = session.get(Connection, connection_id)
        if not connection or not connection.linkedin_url:
            return False

        try:
            profile_data = fetch_linkedin_profile(connection.linkedin_url)
            if not profile_data:
                return False

            # Check for error in response
            if profile_data.get("error"):
                print(f"RapidAPI returned error: {profile_data.get('message', 'Unknown')}")
                return False

            # Store full response in raw_enrichment
            connection.raw_enrichment = profile_data

            # Extract activity_log
            activity_log = extract_activity_log(profile_data)
            if activity_log:
                existing = connection.activity_log or []
                existing_urls = {a.get("url") for a in existing if a.get("url")}
                for item in activity_log:
                    if item.get("url") and item.get("url") not in existing_urls:
                        existing.append(item)
                connection.activity_log = existing

            # Update denormalized fields from RapidAPI response
            data = profile_data.get("data", profile_data)

            # Company
            if data.get("company"):
                connection.current_company = data.get("company")

            # Role - try multiple sources
            if data.get("title"):
                connection.current_role = data.get("title")
            elif data.get("headline"):
                # Extract role from headline (before "|" or "at")
                headline = data.get("headline", "")
                if " | " in headline:
                    connection.current_role = headline.split(" | ")[0].strip()
                elif " at " in headline.lower():
                    connection.current_role = headline.lower().split(" at ")[0].strip().title()
                else:
                    # Use first 100 chars of headline as role
                    connection.current_role = headline[:100]

            # Location
            if data.get("location"):
                connection.location = data.get("location")
            elif data.get("city"):
                location_parts = [data.get("city"), data.get("country")]
                connection.location = ", ".join(p for p in location_parts if p)

            connection.enriched_at = datetime.utcnow()
            connection.updated_at = datetime.utcnow()

            session.add(connection)
            return True

        except Exception as e:
            print(f"Error updating profile for {connection_id}: {e}")
            return False


def enrich_connections_batch(
    connection_ids: list[str],
    progress_callback=None,
) -> dict:
    """
    Enrich multiple connections in batch.

    Args:
        connection_ids: List of connection UUIDs to enrich
        progress_callback: Optional callback(current, total) for progress

    Returns:
        Dict with counts: {"success": N, "failed": N, "errors": [...]}
    """
    results = {"success": 0, "failed": 0, "errors": []}
    total = len(connection_ids)

    for i, conn_id in enumerate(connection_ids):
        try:
            if update_connection_from_profile(conn_id):
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{conn_id}: Failed to fetch profile")
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{conn_id}: {str(e)[:50]}")

        if progress_callback:
            progress_callback(i + 1, total)

    return results


def _get_mock_profile_data() -> dict:
    """Return mock profile data for development."""
    return {
        "data": {
            "full_name": "John Doe",
            "first_name": "John",
            "last_name": "Doe",
            "headline": "Senior Product Manager | AI Enthusiast",
            "title": "Senior Product Manager",
            "company": "Acme Corp",
            "current_company_name": "Acme Corp",
            "current_company_position": "Senior Product Manager",
            "location": "San Francisco, CA",
            "city": "San Francisco",
            "country": "United States",
            "about": "Passionate about building products that matter.",
            "followers_count": 2500,
            "connections_count": 1500,
            "experience": [
                {
                    "title": "Senior Product Manager",
                    "company_name": "Acme Corp",
                    "start_date": "2022-01",
                    "end_date": None,
                    "is_current": True,
                },
                {
                    "title": "Product Manager",
                    "company_name": "StartupXYZ",
                    "start_date": "2019-06",
                    "end_date": "2021-12",
                    "is_current": False,
                },
            ],
            "education": [
                {
                    "school_name": "Stanford University",
                    "degree": "MBA",
                    "field_of_study": "Business Administration",
                }
            ],
            "skills": ["Product Management", "Strategy", "AI/ML", "Leadership"],
        },
        "_fetched_at": datetime.utcnow().isoformat(),
        "_source": "rapidapi_mock",
    }
