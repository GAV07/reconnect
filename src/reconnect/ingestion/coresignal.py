"""Coresignal integration placeholder for profile enrichment."""

from datetime import datetime
from typing import Optional

from reconnect.config import settings
from reconnect.database.engine import get_session
from reconnect.database.models import Connection


def fetch_profile_enrichment(linkedin_url: str) -> Optional[dict]:
    """
    Fetch profile enrichment data from Coresignal.

    PLACEHOLDER: Replace with actual Coresignal API call when ready.

    Args:
        linkedin_url: LinkedIn profile URL

    Returns:
        Dict with career data, or None if fetch fails

    Note:
        Returns mock data since Coresignal is not yet integrated.
    """
    if settings.coresignal_api_key:
        # TODO: Implement actual Coresignal API call
        # import requests
        # response = requests.get(
        #     "https://api.coresignal.com/v2/linkedin/profile",
        #     params={"url": linkedin_url},
        #     headers={"Authorization": f"Bearer {settings.coresignal_api_key}"}
        # )
        # return response.json()
        pass

    # Return mock data for development
    return {
        "headline": "Product Manager | Building the future of AI",
        "summary": "Passionate about creating products that make a difference. "
        "10+ years experience in tech.",
        "industry": "Technology",
        "location": "San Francisco, CA",
        "connections_count": 500,
        "positions": [
            {
                "title": "Senior Product Manager",
                "company_name": "Acme Corp",
                "start_date": "2022-01",
                "end_date": None,
                "location": "San Francisco, CA",
            },
            {
                "title": "Product Manager",
                "company_name": "StartupXYZ",
                "start_date": "2019-06",
                "end_date": "2021-12",
            },
        ],
        "education": [
            {
                "school_name": "Stanford University",
                "degree": "MBA",
                "field_of_study": "Business Administration",
                "end_year": 2019,
            }
        ],
        "skills": ["Product Management", "Strategy", "AI/ML", "Leadership"],
        "source": "coresignal_mock",
        "fetched_at": datetime.utcnow().isoformat(),
    }


def enrich_connection(connection_id: str) -> bool:
    """
    Fetch and store enrichment data for a connection.

    Args:
        connection_id: UUID of the connection to enrich

    Returns:
        True if successful, False otherwise
    """
    with get_session() as session:
        connection = session.get(Connection, connection_id)
        if not connection or not connection.linkedin_url:
            return False

        try:
            enrichment_data = fetch_profile_enrichment(connection.linkedin_url)
            if not enrichment_data:
                return False

            # Store raw enrichment
            connection.raw_enrichment = enrichment_data

            # Update denormalized fields from enrichment
            positions = enrichment_data.get("positions", [])
            if positions:
                current = positions[0]
                connection.current_role = current.get("title")
                connection.current_company = current.get("company_name")

            connection.location = enrichment_data.get("location")
            connection.enriched_at = datetime.utcnow()
            connection.updated_at = datetime.utcnow()

            session.add(connection)

            return True

        except Exception as e:
            print(f"Error enriching {connection_id}: {e}")
            return False
