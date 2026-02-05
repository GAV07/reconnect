"""LLM prose generation for personalized outreach."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from openai import OpenAI

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection, UserProfile
from src.llm.prompts import SYSTEM_PROMPT, build_prose_prompt, format_user_context


@dataclass
class ProseResult:
    """Result of prose generation."""

    summary: str
    reason_to_reach_out: str
    suggested_message: str
    talking_points: list[str]
    generated_at: datetime

    def to_json(self) -> str:
        """Serialize to JSON for caching."""
        return json.dumps(
            {
                "summary": self.summary,
                "reason_to_reach_out": self.reason_to_reach_out,
                "suggested_message": self.suggested_message,
                "talking_points": self.talking_points,
                "generated_at": self.generated_at.isoformat(),
            }
        )

    @classmethod
    def from_json(cls, data: str) -> "ProseResult":
        """Deserialize from cached JSON."""
        d = json.loads(data)
        return cls(
            summary=d["summary"],
            reason_to_reach_out=d["reason_to_reach_out"],
            suggested_message=d["suggested_message"],
            talking_points=d["talking_points"],
            generated_at=datetime.fromisoformat(d["generated_at"]),
        )


def extract_recent_posts(activity_log: Optional[list[dict]], limit: int = 3) -> list[dict]:
    """Extract most recent posts from activity log."""
    if not activity_log:
        return []
    return activity_log[:limit]


def format_post_for_prompt(post: dict) -> str:
    """Format a single post for the LLM prompt."""
    content = post.get("content", "")[:300]  # Truncate long posts
    return f"- {content}"


def extract_career_info(raw_enrichment: Optional[dict]) -> dict:
    """
    Extract relevant career information from Apify enrichment data.

    Uses actual Apify field names:
    - jobTitle, companyName (current job)
    - experiences[] (job history)
    - headline, about
    - skills[] (array of {title: ...})
    """
    if not raw_enrichment:
        return {}

    # Extract skills - handle both {title: ...} format and plain strings
    skills_raw = raw_enrichment.get("skills", [])
    skills = []
    for s in skills_raw[:10]:
        if isinstance(s, dict):
            skills.append(s.get("title", ""))
        else:
            skills.append(str(s))
    skills = [s for s in skills if s]  # Filter empty

    # Extract experiences for career trajectory
    experiences = raw_enrichment.get("experiences", [])
    previous_roles = []
    for exp in experiences[1:4]:  # Skip current, get next 3
        title = exp.get("title", "")
        company = exp.get("companyName", "")
        if title and company:
            previous_roles.append(f"{title} at {company}")

    return {
        "headline": raw_enrichment.get("headline", ""),
        "about": raw_enrichment.get("about", "")[:500] if raw_enrichment.get("about") else "",
        "current_title": raw_enrichment.get("jobTitle", ""),
        "current_company": raw_enrichment.get("companyName", ""),
        "company_industry": raw_enrichment.get("companyIndustry", ""),
        "total_experience_years": raw_enrichment.get("totalExperienceYears"),
        "skills": skills,
        "previous_roles": previous_roles,
        "is_creator": raw_enrichment.get("isCreator", False),
        "connections": raw_enrichment.get("connections", 0),
        "followers": raw_enrichment.get("followers", 0),
    }


def generate_prose(connection_id: str) -> ProseResult:
    """
    Generate personalized outreach prose for a connection.

    Args:
        connection_id: The UUID of the connection

    Returns:
        ProseResult with summary, reason, message, and talking points

    Raises:
        ValueError: If connection not found or OpenAI API key not set
    """
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in .env")

    # Fetch data
    with get_session() as session:
        connection = session.get(Connection, connection_id)
        if not connection:
            raise ValueError(f"Connection not found: {connection_id}")

        user_profile = session.get(UserProfile, 1)  # Single user

    # Extract data from enrichment
    career_info = extract_career_info(connection.raw_enrichment)
    recent_posts = extract_recent_posts(connection.activity_log)

    # Format posts for prompt
    if recent_posts:
        activity_text = "\n".join(format_post_for_prompt(p) for p in recent_posts)
    else:
        activity_text = "- No recent posts available"

    # Format career trajectory
    career_trajectory = ""
    if career_info.get("previous_roles"):
        career_trajectory = f"\nPrevious roles: {', '.join(career_info['previous_roles'])}"

    # Add experience context
    if career_info.get("total_experience_years"):
        career_trajectory += f"\nTotal experience: {career_info['total_experience_years']:.0f} years"

    # User context
    user_context = ""
    if user_profile:
        user_context = format_user_context(
            name=user_profile.name,
            current_role=user_profile.current_role or "",
            company=user_profile.company or "",
            industry=user_profile.industry or "",
            goals=user_profile.goals or "",
            interests=user_profile.interests or "",
        )

    # Build prompt
    prompt = build_prose_prompt(
        user_context=user_context,
        contact_name=connection.name,
        current_role=connection.current_role or career_info.get("current_title", "Unknown"),
        current_company=connection.current_company or career_info.get("current_company", "Unknown"),
        headline=career_info.get("headline", "N/A"),
        skills=career_info.get("skills", []),
        career_trajectory=career_trajectory,
        activity_text=activity_text,
    )

    # Call OpenAI
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=settings.openai_max_tokens,
        temperature=settings.openai_temperature,
        response_format={"type": "json_object"},
    )

    # Parse response
    content = response.choices[0].message.content
    data = json.loads(content)

    return ProseResult(
        summary=data.get("summary", ""),
        reason_to_reach_out=data.get("reason_to_reach_out", ""),
        suggested_message=data.get("suggested_message", ""),
        talking_points=data.get("talking_points", []),
        generated_at=datetime.utcnow(),
    )


def get_or_generate_prose(connection_id: str, force_refresh: bool = False) -> ProseResult:
    """
    Get cached prose or generate new prose for a connection.

    Args:
        connection_id: The UUID of the connection
        force_refresh: If True, regenerate even if cache is valid

    Returns:
        ProseResult with summary, reason, message, and talking points
    """
    with get_session() as session:
        connection = session.get(Connection, connection_id)
        if not connection:
            raise ValueError(f"Connection not found: {connection_id}")

        # Check cache validity (7 days by default)
        if not force_refresh and connection.cached_summary and connection.cached_summary_at:
            cache_age = (datetime.utcnow() - connection.cached_summary_at).days
            if cache_age < settings.cache_ttl_days:
                return ProseResult.from_json(connection.cached_summary)

    # Generate fresh prose
    result = generate_prose(connection_id)

    # Update cache
    with get_session() as session:
        connection = session.get(Connection, connection_id)
        if connection:
            connection.cached_summary = result.to_json()
            connection.cached_summary_at = datetime.utcnow()
            session.add(connection)

    return result


def generate_outreach_message(
    connection: Connection,
    user_profile: UserProfile,
    channel: str = "email",
) -> str:
    """
    Generate a personalized outreach message for a connection.

    Args:
        connection: Connection to generate message for
        user_profile: User profile for context
        channel: "email" or "linkedin"

    Returns:
        Generated message string
    """
    if not settings.openai_api_key:
        # Fallback template
        first_name = connection.name.split()[0] if connection.name else "there"
        return f"Hi {first_name},\n\nHope you're doing well! Would love to catch up sometime."

    # Build context
    career_info = extract_career_info(connection.raw_enrichment)
    recent_posts = extract_recent_posts(connection.activity_log)

    # Format activity
    activity_context = ""
    if recent_posts:
        activity_context = f"\nRecent activity: {recent_posts[0].get('content', '')[:150]}"

    # Conversation context
    convo_context = ""
    if connection.conversation_summary:
        convo_context = f"\nPrevious conversation: {connection.conversation_summary}"
    elif connection.message_count and connection.message_count > 0:
        convo_context = f"\nHave exchanged {connection.message_count} messages before."

    prompt = f"""Generate a short, personalized {channel} message to reconnect with this contact.

Sender: {user_profile.name or 'Me'}
- Role: {user_profile.current_role or 'Professional'}
- Company: {user_profile.company or 'N/A'}
- Goals: {user_profile.goals or 'Network expansion'}

Recipient: {connection.name}
- Role: {connection.current_role or career_info.get('current_title', 'Unknown')}
- Company: {connection.current_company or career_info.get('current_company', 'Unknown')}
- Headline: {career_info.get('headline', 'N/A')}{activity_context}{convo_context}

Guidelines:
- Keep it brief (3-4 sentences max for LinkedIn, 4-5 for email)
- Reference something specific if possible (recent post, shared background, etc.)
- Be genuine, not salesy
- Include a soft call to action (grab coffee, catch up, etc.)
- {"Use casual tone for LinkedIn DM" if channel == "linkedin" else "Use professional but warm tone for email"}

Return ONLY the message text, no subject line or explanations."""

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        first_name = connection.name.split()[0] if connection.name else "there"
        return f"Hi {first_name},\n\nHope you're doing well! Would love to catch up sometime."
