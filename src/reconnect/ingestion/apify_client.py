"""Apify integration for LinkedIn profile enrichment."""

from datetime import datetime
from typing import Optional

from apify_client import ApifyClient

from reconnect.config import settings
from reconnect.database.engine import get_session
from reconnect.database.models import Connection


def get_apify_client() -> Optional[ApifyClient]:
    """Get Apify client if API key is configured."""
    if not settings.apify_api_key:
        return None
    return ApifyClient(settings.apify_api_key)


def fetch_linkedin_profile(linkedin_url: str) -> Optional[dict]:
    """
    Fetch LinkedIn profile data using Apify.

    Args:
        linkedin_url: LinkedIn profile URL

    Returns:
        Full Apify response dict, or None if fetch fails

    Note:
        Returns mock data if APIFY_API_KEY is not set.
    """
    client = get_apify_client()

    if not client:
        # Return mock data for development
        return _get_mock_profile_data()

    try:
        # Run the LinkedIn profile scraper actor
        # Actor: 2SyF0bVxmgGr8IVCZ uses profileUrls input format
        run_input = {
            "profileUrls": [linkedin_url],
        }

        run = client.actor(settings.apify_actor_id).call(run_input=run_input)

        # Get results from the dataset
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

        if not items:
            return None

        # Return the full profile data
        profile_data = items[0]
        profile_data["_fetched_at"] = datetime.utcnow().isoformat()
        profile_data["_source"] = "apify"

        return profile_data

    except Exception as e:
        print(f"Apify fetch error: {e}")
        return None


def _get_mock_profile_data() -> dict:
    """Return mock profile data matching real Apify structure."""
    return {
        "firstName": "John",
        "lastName": "Doe",
        "fullName": "John Doe",
        "headline": "Senior Product Manager | AI Enthusiast | Building the Future",
        "about": "Passionate about creating products that make a difference. 10+ years in tech, from engineer to PM.",
        "connections": 1500,
        "followers": 2300,
        "jobTitle": "Senior Product Manager",
        "jobStartedOn": "1-2022",
        "jobStillWorking": True,
        "companyName": "Acme Corp",
        "companyIndustry": "Software Development",
        "companyWebsite": "https://acme.com",
        "companySize": "201-500",
        "currentJobDuration": "2 yrs 6 mos",
        "currentJobDurationInYrs": 2.5,
        "addressCountryOnly": "United States",
        "addressWithCountry": "San Francisco, California, United States",
        "profilePic": "https://example.com/photo.jpg",
        "isPremium": False,
        "isVerified": True,
        "isCreator": True,
        "isInfluencer": False,
        "totalExperienceYears": 12.5,
        "experiencesCount": 5,
        "experiences": [
            {
                "companyName": "Acme Corp",
                "companyIndustry": "Software Development",
                "companySize": "201-500",
                "companyWebsite": "https://acme.com",
                "title": "Senior Product Manager",
                "jobDescription": "Leading product strategy for AI-powered features.",
                "jobStartedOn": "1-2022",
                "jobEndedOn": None,
                "jobStillWorking": True,
                "employmentType": "Full-time",
            },
            {
                "companyName": "StartupXYZ",
                "companyIndustry": "Technology",
                "companySize": "11-50",
                "title": "Product Manager",
                "jobDescription": "Built and launched 3 major product lines.",
                "jobStartedOn": "6-2019",
                "jobEndedOn": "12-2021",
                "jobStillWorking": False,
                "employmentType": "Full-time",
            },
            {
                "companyName": "BigTech Inc",
                "companyIndustry": "Technology",
                "companySize": "10000+",
                "title": "Software Engineer",
                "jobDescription": "Full-stack development on customer-facing products.",
                "jobStartedOn": "3-2015",
                "jobEndedOn": "5-2019",
                "jobStillWorking": False,
                "employmentType": "Full-time",
            },
        ],
        "updates": [
            {
                "postText": "Excited to announce our new AI-powered feature launch! After months of hard work with an incredible team, we're finally ready to share what we've been building. The future of product demos is here. #ProductManagement #AI #Innovation",
                "postLink": "https://linkedin.com/posts/johndoe-1",
                "type": "Post",
            },
            {
                "postText": "Just got back from the Product Leadership Summit. Key takeaway: the best PMs aren't just building features, they're solving problems customers didn't even know they had. Great conversations with fellow product leaders!",
                "postLink": "https://linkedin.com/posts/johndoe-2",
                "type": "Post",
            },
            {
                "postText": "Reflecting on my journey from engineer to PM. The transition taught me that technical skills are just the foundation - understanding customer psychology is what makes the difference. Happy to chat with anyone considering the switch!",
                "postLink": "https://linkedin.com/posts/johndoe-3",
                "type": "Post",
            },
        ],
        "skills": [
            {"title": "Product Management"},
            {"title": "Product Strategy"},
            {"title": "Agile Methodologies"},
            {"title": "AI/ML"},
            {"title": "User Research"},
            {"title": "Data Analysis"},
            {"title": "Cross-functional Leadership"},
        ],
        "educations": [
            {
                "schoolName": "Stanford University",
                "degree": "MBA",
                "fieldOfStudy": "Business Administration",
                "startYear": 2017,
                "endYear": 2019,
            },
            {
                "schoolName": "UC Berkeley",
                "degree": "BS",
                "fieldOfStudy": "Computer Science",
                "startYear": 2011,
                "endYear": 2015,
            },
        ],
        "languages": [
            {"name": "English", "proficiency": "Native"},
            {"name": "Spanish", "proficiency": "Professional"},
        ],
        "_fetched_at": datetime.utcnow().isoformat(),
        "_source": "apify_mock",
    }


def extract_activity_log(profile_data: dict) -> list[dict]:
    """
    Extract and normalize posts/updates into activity_log format.

    Args:
        profile_data: Full Apify profile response

    Returns:
        List of activity items in normalized format
    """
    activity_log = []

    for update in profile_data.get("updates", []):
        activity_log.append({
            "type": "post",
            "content": update.get("postText", ""),
            "url": update.get("postLink", ""),
            "post_type": update.get("type", "Post"),
            "source": profile_data.get("_source", "apify"),
        })

    return activity_log


def update_connection_activity(connection_id: str) -> bool:
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

            # Store full response in raw_enrichment
            connection.raw_enrichment = profile_data

            # Extract activity_log from updates
            activity_log = extract_activity_log(profile_data)

            # Merge with existing activity (dedupe by URL)
            existing = connection.activity_log or []
            existing_urls = {a.get("url") for a in existing if a.get("url")}

            for item in activity_log:
                if item.get("url") and item.get("url") not in existing_urls:
                    existing.append(item)

            connection.activity_log = existing

            # Update denormalized fields from Apify field names
            if profile_data.get("jobTitle"):
                connection.current_role = profile_data.get("jobTitle")
            if profile_data.get("companyName"):
                connection.current_company = profile_data.get("companyName")
            if profile_data.get("addressCountryOnly"):
                connection.location = profile_data.get("addressCountryOnly")
            elif profile_data.get("addressWithCountry"):
                connection.location = profile_data.get("addressWithCountry")

            connection.enriched_at = datetime.utcnow()
            connection.updated_at = datetime.utcnow()

            session.add(connection)

            return True

        except Exception as e:
            print(f"Error updating activity for {connection_id}: {e}")
            return False


def enrich_connections_batch(connection_ids: list[str], progress_callback=None) -> dict:
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
            if update_connection_activity(conn_id):
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{conn_id}: Failed to fetch profile")
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{conn_id}: {str(e)}")

        if progress_callback:
            progress_callback(i + 1, total)

    return results
