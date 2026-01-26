"""LLM-based scoring for connection prioritization."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from openai import OpenAI

from reconnect.config import settings
from reconnect.database.engine import get_session
from reconnect.database.models import Connection, UserProfile


SCORING_SYSTEM_PROMPT = """You are an expert at professional networking and relationship building.
Your task is to evaluate how valuable it would be for someone to reconnect with a professional contact,
based on the user's goals, interests, and the contact's profile and recent activity.

Score from 0-100 where:
- 90-100: Perfect match - strong alignment with goals, recent relevant activity, clear conversation starters
- 70-89: High value - good alignment with interests/goals, worth reaching out soon
- 50-69: Moderate value - some relevance, could be useful connection
- 30-49: Low value - limited alignment, not a priority
- 0-29: Not relevant - no clear reason to reconnect

Always respond with valid JSON."""


@dataclass
class ScoreResult:
    """Result of scoring a connection."""

    score: float  # 0-100
    reasoning: str  # Why this score
    key_factors: list[str]  # Bullet points of what influenced the score
    conversation_hooks: list[str]  # Potential conversation starters if score is high


def build_scoring_prompt(
    user_profile: UserProfile,
    connection: Connection,
) -> str:
    """Build the prompt for scoring a connection."""

    # User context
    user_context = f"""USER'S PROFILE:
- Name: {user_profile.name or 'Not specified'}
- Current role: {user_profile.current_role or 'Not specified'}
- Company: {user_profile.company or 'Not specified'}
- Industry: {user_profile.industry or 'Not specified'}
- Networking goals: {user_profile.goals or 'General networking'}
- Interests/topics: {user_profile.interests or 'Not specified'}
"""

    # Contact info from enrichment
    enrichment = connection.raw_enrichment or {}

    # Extract skills
    skills_raw = enrichment.get("skills", [])
    skills = []
    for s in skills_raw[:8]:
        if isinstance(s, dict):
            skills.append(s.get("title", ""))
        else:
            skills.append(str(s))
    skills_str = ", ".join([s for s in skills if s]) or "N/A"

    # Extract recent activity
    activity_log = connection.activity_log or []
    if activity_log:
        posts = []
        for item in activity_log[:3]:
            content = item.get("content", "")[:200]
            if content:
                posts.append(f"- {content}")
        activity_text = "\n".join(posts) if posts else "No recent posts"
    else:
        activity_text = "No recent activity available"

    # Career trajectory
    experiences = enrichment.get("experiences", [])
    career_trajectory = ""
    if len(experiences) > 1:
        prev_roles = []
        for exp in experiences[1:3]:
            title = exp.get("title", "")
            company = exp.get("companyName", "")
            if title and company:
                prev_roles.append(f"{title} at {company}")
        if prev_roles:
            career_trajectory = f"\nPrevious roles: {', '.join(prev_roles)}"

    # Job change detection
    job_started = enrichment.get("jobStartedOn", "")
    is_recent_job_change = False
    if job_started:
        # Format is "M-YYYY" like "8-2024"
        try:
            parts = job_started.split("-")
            if len(parts) == 2:
                month, year = int(parts[0]), int(parts[1])
                job_start_date = datetime(year, month, 1)
                months_in_role = (datetime.utcnow() - job_start_date).days / 30
                is_recent_job_change = months_in_role < 6
        except (ValueError, IndexError):
            pass

    contact_context = f"""CONTACT'S PROFILE:
- Name: {connection.name}
- Current role: {connection.current_role or enrichment.get('jobTitle', 'Unknown')}
- Company: {connection.current_company or enrichment.get('companyName', 'Unknown')}
- Industry: {enrichment.get('companyIndustry', 'Unknown')}
- Headline: {enrichment.get('headline', 'N/A')}
- Location: {connection.location or enrichment.get('addressWithCountry', 'Unknown')}
- Skills: {skills_str}
- Experience: {enrichment.get('totalExperienceYears', 'Unknown')} years
- Is a LinkedIn Creator: {enrichment.get('isCreator', False)}
- Recent job change (< 6 months): {is_recent_job_change}{career_trajectory}

RECENT LINKEDIN ACTIVITY:
{activity_text}
"""

    return f"""{user_context}
{contact_context}

TASK:
Evaluate how valuable it would be for the user to reconnect with this contact based on:
1. Alignment with user's stated networking goals
2. Overlap with user's interests and industry
3. Potential for mutual value exchange
4. Quality of conversation hooks (recent activity, job changes, shared interests)
5. Professional relevance and network value

Respond in JSON format:
{{
  "score": <0-100>,
  "reasoning": "<2-3 sentence explanation of the score>",
  "key_factors": ["<factor 1>", "<factor 2>", ...],
  "conversation_hooks": ["<hook 1>", "<hook 2>", ...]
}}

If there's no clear reason to reconnect, give a low score and explain why."""


def score_connection(connection_id: str) -> Optional[ScoreResult]:
    """
    Score a single connection using LLM.

    Args:
        connection_id: UUID of the connection to score

    Returns:
        ScoreResult with score, reasoning, and hooks, or None if scoring fails
    """
    if not settings.openai_api_key:
        return None

    with get_session() as session:
        connection = session.get(Connection, connection_id)
        if not connection:
            return None

        user_profile = session.get(UserProfile, 1)
        if not user_profile or not user_profile.goals:
            # Can't score without user context
            return None

        # Build prompt
        prompt = build_scoring_prompt(user_profile, connection)

        # Call OpenAI
        client = OpenAI(api_key=settings.openai_api_key)

        try:
            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": SCORING_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=400,
                temperature=0.3,  # Lower temperature for more consistent scoring
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            result = ScoreResult(
                score=float(data.get("score", 0)),
                reasoning=data.get("reasoning", ""),
                key_factors=data.get("key_factors", []),
                conversation_hooks=data.get("conversation_hooks", []),
            )

            # Update the connection with score
            connection.reconnect_score = result.score
            connection.score_reasoning = json.dumps({
                "reasoning": result.reasoning,
                "key_factors": result.key_factors,
                "conversation_hooks": result.conversation_hooks,
            })
            connection.scored_at = datetime.utcnow()
            session.add(connection)

            return result

        except Exception as e:
            print(f"Scoring error for {connection_id}: {e}")
            return None


def score_connections_batch(
    connection_ids: list[str],
    progress_callback=None,
) -> dict:
    """
    Score multiple connections.

    Args:
        connection_ids: List of connection UUIDs to score
        progress_callback: Optional callback(current, total) for progress

    Returns:
        Dict with counts: {"scored": N, "failed": N, "errors": [...]}
    """
    results = {"scored": 0, "failed": 0, "errors": []}
    total = len(connection_ids)

    for i, conn_id in enumerate(connection_ids):
        try:
            result = score_connection(conn_id)
            if result:
                results["scored"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{conn_id}: Failed to score")
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{conn_id}: {str(e)}")

        if progress_callback:
            progress_callback(i + 1, total)

    return results


def get_top_connections(limit: int = 20) -> list[tuple[Connection, dict]]:
    """
    Get top-scored connections with their reasoning.

    Returns:
        List of (Connection, reasoning_dict) tuples sorted by score descending
    """
    with get_session() as session:
        from sqlmodel import select

        query = (
            select(Connection)
            .where(Connection.reconnect_score.isnot(None))
            .order_by(Connection.reconnect_score.desc())
            .limit(limit)
        )

        connections = session.exec(query).all()

        results = []
        for conn in connections:
            # Load all attributes before session closes
            _ = conn.id
            _ = conn.name
            _ = conn.current_role
            _ = conn.current_company
            _ = conn.reconnect_score
            _ = conn.enriched_at

            reasoning = {}
            if conn.score_reasoning:
                try:
                    reasoning = json.loads(conn.score_reasoning)
                except json.JSONDecodeError:
                    pass

            results.append((conn, reasoning))

        return results
