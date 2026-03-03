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

            # Store the profile fields (unwrap "data" envelope if present)
            data = profile_data.get("data", profile_data)
            connection.raw_enrichment = data

            # Extract activity_log (use full response — posts may be at top level)
            activity_log = extract_activity_log(profile_data)
            if activity_log:
                existing = connection.activity_log or []
                existing_urls = {a.get("url") for a in existing if a.get("url")}
                for item in activity_log:
                    if item.get("url") and item.get("url") not in existing_urls:
                        existing.append(item)
                connection.activity_log = existing

            # Update denormalized fields from the unwrapped data
            # Company
            if data.get("company"):
                connection.current_company = data["company"]

            # Role — prefer job_title, fall back to headline parsing
            if data.get("job_title"):
                connection.current_role = data["job_title"]
            elif data.get("headline"):
                headline = data["headline"]
                if " | " in headline:
                    connection.current_role = headline.split(" | ")[0].strip()
                elif " at " in headline.lower():
                    connection.current_role = headline.lower().split(" at ")[0].strip().title()
                else:
                    connection.current_role = headline[:100]

            # Location
            if data.get("location"):
                connection.location = data["location"]
            elif data.get("city"):
                location_parts = [data.get("city"), data.get("state"), data.get("country")]
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
    """Return mock profile data matching RapidAPI fresh-linkedin-profile-data format."""
    return {
        "data": {
            "full_name": "John Doe",
            "first_name": "John",
            "last_name": "Doe",
            "headline": "Senior Product Manager | AI Enthusiast",
            "job_title": "Senior Product Manager",
            "company": "Acme Corp",
            "company_industry": "Technology",
            "company_website": "https://acmecorp.com",
            "company_domain": "acmecorp.com",
            "location": "San Francisco, California, United States",
            "city": "San Francisco",
            "state": "California",
            "country": "United States",
            "about": "Passionate about building products that matter.",
            "follower_count": 2500,
            "connection_count": 1500,
            "is_creator": False,
            "is_premium": True,
            "is_influencer": False,
            "current_company_join_month": 3,
            "current_company_join_year": 2022,
            "current_job_duration": "4 yrs",
            "profile_image_url": "",
            "experiences": [
                {
                    "title": "Senior Product Manager",
                    "company": "Acme Corp",
                    "company_linkedin_url": "",
                    "date_range": "Mar 2022 - Present",
                    "duration": "4 yrs",
                    "start_month": 3,
                    "start_year": 2022,
                    "end_month": "",
                    "end_year": "",
                    "is_current": True,
                    "description": "Leading product strategy for enterprise platform.",
                    "location": "San Francisco, CA",
                    "skills": "Product Management · Strategy · AI/ML",
                },
                {
                    "title": "Product Manager",
                    "company": "StartupXYZ",
                    "company_linkedin_url": "",
                    "date_range": "Jun 2019 - Dec 2021",
                    "duration": "2 yrs 7 mos",
                    "start_month": 6,
                    "start_year": 2019,
                    "end_month": 12,
                    "end_year": 2021,
                    "is_current": False,
                    "description": "",
                    "location": "",
                    "skills": "Leadership · Agile Methodologies",
                },
            ],
            "educations": [
                {
                    "school": "Stanford University",
                    "degree": "MBA",
                    "field_of_study": "Business Administration",
                    "date_range": "2017 - 2019",
                    "start_year": 2017,
                    "end_year": 2019,
                },
            ],
        },
        "message": "ok",
    }
