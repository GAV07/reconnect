"""LLM-based scoring for connection prioritization."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from openai import OpenAI

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection, UserProfile, get_enrichment_data


SCORING_SYSTEM_PROMPT = """You are an expert at professional networking and relationship building.
Your task is to evaluate how valuable it would be for someone to reconnect with a professional contact,
using a structured rubric with 5 independent dimensions. Score each dimension separately.

SCORING RUBRIC:

1. Goal Alignment (0-25 points)
   How directly relevant is this contact to the user's stated networking goals?
   - 20-25: Core to their goals (same domain, direct collaborator potential)
   - 12-19: Clearly relevant (adjacent space, useful perspective)
   - 5-11: Tangentially related
   - 0-4: No meaningful alignment

2. Industry & Interest Overlap (0-20 points)
   Shared industry, topics, expertise areas with the user?
   - 16-20: Same industry + shared topics/expertise
   - 10-15: Same or adjacent industry
   - 4-9: Some topical overlap
   - 0-3: Different worlds

3. Mutual Value Potential (0-20 points)
   Could both sides benefit? Complementary skills, appropriate seniority fit?
   - 16-20: Clear two-way value (complementary skills, peer-level, intro potential)
   - 10-15: Likely one-way value or moderate fit
   - 4-9: Unclear or limited value exchange
   - 0-3: Mismatch in seniority/skills/needs

4. Conversation Hooks (0-20 points)
   Are there tangible, timely reasons to reach out NOW?
   - 16-20: Multiple strong hooks (recent job change + relevant posts + shared experience)
   - 10-15: One solid hook (job change OR active posting OR shared event)
   - 4-9: Weak hooks (generic activity, old news)
   - 0-3: Nothing timely to reference

5. Network Reach (0-15 points)
   Amplification potential - are they a connector, creator, or influencer?
   - 12-15: Active creator/influencer with large network (500+ connections, regular posts)
   - 7-11: Well-connected professional (moderate network, some visibility)
   - 3-6: Average network presence
   - 0-2: Minimal or no network visibility

CALIBRATION EXAMPLES:

High scorer (~85): VP of Product at a SaaS company when user's goal is "break into product management".
Same industry, recently posted about PM hiring, 10k followers, previously worked at user's target company.
Scores: Goal=23, Industry=18, Mutual=16, Hooks=18, Reach=12

Medium scorer (~50): Senior Engineer at a bank when user is in tech/startups.
Adjacent industry, no recent activity, decent seniority but different domain.
Scores: Goal=8, Industry=10, Mutual=12, Hooks=6, Reach=8

Low scorer (~20): Student at a university, no shared industry, no activity.
Scores: Goal=2, Industry=3, Mutual=4, Hooks=2, Reach=2

Always respond with valid JSON."""


@dataclass
class ScoreResult:
    """Result of scoring a connection."""

    score: float  # 0-100
    reasoning: str  # Why this score
    key_factors: list[str]  # Bullet points of what influenced the score
    conversation_hooks: list[str]  # Potential conversation starters if score is high
    dimension_scores: dict[str, int] = None  # Per-dimension breakdown

    def __post_init__(self):
        if self.dimension_scores is None:
            self.dimension_scores = {}


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

    # Add user's posting themes if available
    if hasattr(user_profile, 'posting_themes') and user_profile.posting_themes:
        themes_str = ", ".join(user_profile.posting_themes[:10])
        user_context += f"- Content themes: {themes_str}\n"

    # Add public persona if available
    if hasattr(user_profile, 'public_persona_summary') and user_profile.public_persona_summary:
        user_context += f"- Professional persona: {user_profile.public_persona_summary}\n"

    # Contact info from enrichment (unwrap nested "data" key if present)
    enrichment = get_enrichment_data(connection)

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

    # Build engagement context
    engagement_context = ""
    if hasattr(connection, 'engagement_score') and connection.engagement_score is not None:
        engagement_context = f"""
ENGAGEMENT HISTORY:
- Engagement score: {connection.engagement_score:.0f}/100
- Last engagement: {connection.last_engagement_date.strftime('%Y-%m-%d') if connection.last_engagement_date else 'N/A'}
- Engagement direction: {connection.engagement_direction or 'N/A'}
- Endorsements exchanged: {connection.endorsement_count or 0}
- Has recommendation: {'Yes' if connection.has_recommendation else 'No'}
"""

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
{engagement_context}
RECENT LINKEDIN ACTIVITY:
{activity_text}
"""

    return f"""{user_context}
{contact_context}

TASK:
Score this contact using the 5-dimension rubric. Evaluate each dimension independently, then sum for the total.
Consider engagement history (reactions, comments, endorsements) as a signal of existing rapport when scoring.

Respond in JSON format:
{{
  "dimension_scores": {{
    "goal_alignment": <0-25>,
    "industry_overlap": <0-20>,
    "mutual_value": <0-20>,
    "conversation_hooks": <0-20>,
    "network_reach": <0-15>
  }},
  "score": <sum of all dimensions, 0-100>,
  "reasoning": "<2-3 sentence explanation of the score>",
  "key_factors": ["<factor 1>", "<factor 2>", ...],
  "conversation_hooks": ["<hook 1>", "<hook 2>", ...]
}}

Score each dimension honestly - most contacts will NOT max out every dimension. If there's no clear reason to reconnect, give low dimension scores and explain why."""


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
                max_tokens=600,
                temperature=0.3,  # Lower temperature for more consistent scoring
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            dimension_scores = data.get("dimension_scores", {})

            # Compute total from dimensions if available, otherwise use raw score
            if dimension_scores:
                computed_total = sum(dimension_scores.values())
            else:
                computed_total = float(data.get("score", 0))

            result = ScoreResult(
                score=computed_total,
                reasoning=data.get("reasoning", ""),
                key_factors=data.get("key_factors", []),
                conversation_hooks=data.get("conversation_hooks", []),
                dimension_scores=dimension_scores,
            )

            # Update the connection with score
            connection.reconnect_score = result.score
            connection.score_reasoning = json.dumps({
                "reasoning": result.reasoning,
                "key_factors": result.key_factors,
                "conversation_hooks": result.conversation_hooks,
                "dimension_scores": result.dimension_scores,
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
