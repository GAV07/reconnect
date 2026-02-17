"""Pre-enrichment scoring for Reconnect.

Two-stage scoring to prioritize which contacts to enrich via Apify:
1. Rule-based scoring (free, instant) - uses title/company keywords
2. Batch LLM scoring (cheap) - sends batches for AI evaluation
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from openai import OpenAI
from sqlmodel import select

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection, UserProfile


# Title-based score adjustments
TITLE_BOOST = {
    # Executive
    "founder": 30,
    "co-founder": 30,
    "ceo": 30,
    "cto": 28,
    "cfo": 25,
    "coo": 25,
    "president": 25,
    "partner": 22,
    # VP level
    "vp": 20,
    "vice president": 20,
    "managing director": 20,
    # Director level
    "director": 15,
    "head of": 15,
    # Senior IC
    "principal": 12,
    "staff": 10,
    "senior": 8,
    "lead": 8,
    # Mid level
    "manager": 5,
}

TITLE_PENALIZE = {
    "student": -30,
    "intern": -25,
    "retired": -20,
    "unemployed": -15,
    "seeking": -10,
    "looking for": -10,
    "open to work": -10,
}

# Company-based score adjustments
COMPANY_BOOST = {
    # Big tech (valuable network)
    "google": 10,
    "meta": 10,
    "facebook": 10,
    "apple": 10,
    "amazon": 10,
    "microsoft": 10,
    "netflix": 8,
    # Prestigious companies
    "mckinsey": 12,
    "bain": 12,
    "bcg": 12,
    "goldman": 10,
    "jpmorgan": 10,
    # YC/top tier startups indicators
    "yc": 8,
    "y combinator": 8,
    "sequoia": 8,
    "a16z": 8,
}


@dataclass
class PreScoreResult:
    """Result of pre-scoring a connection."""

    score: float  # 0-100
    tier: int  # 1=enrich, 2=maybe, 3=skip
    factors: list[str]  # What influenced the score


def rule_based_prescore(
    connection: Connection,
    user_profile: Optional[UserProfile] = None,
) -> PreScoreResult:
    """
    Fast rule-based pre-scoring without LLM.

    Args:
        connection: Connection to score
        user_profile: Optional user profile for context

    Returns:
        PreScoreResult with score, tier, and factors
    """
    score = 50.0  # Start at neutral
    factors = []

    title = (connection.current_role or "").lower()
    company = (connection.current_company or "").lower()

    # Title boosts
    for keyword, boost in TITLE_BOOST.items():
        if keyword in title:
            score += boost
            factors.append(f"+{boost} title:{keyword}")
            break  # Only apply one title boost

    # Title penalties
    for keyword, penalty in TITLE_PENALIZE.items():
        if keyword in title:
            score += penalty
            factors.append(f"{penalty} title:{keyword}")

    # Company boosts
    for keyword, boost in COMPANY_BOOST.items():
        if keyword in company:
            score += boost
            factors.append(f"+{boost} company:{keyword}")
            break  # Only apply one company boost

    # User profile matching
    if user_profile:
        # Industry match
        if user_profile.industry:
            user_industry = user_profile.industry.lower()
            if user_industry in company or user_industry in title:
                score += 10
                factors.append("+10 industry_match")

        # Interests match (from goals)
        if user_profile.goals:
            goals_lower = user_profile.goals.lower()
            # Check if contact might be relevant to goals
            goal_keywords = re.findall(r"\b\w{4,}\b", goals_lower)
            for kw in goal_keywords[:5]:
                if kw in title or kw in company:
                    score += 5
                    factors.append(f"+5 goal_match:{kw}")
                    break

    # Has LinkedIn URL (can be enriched)
    if connection.linkedin_url:
        score += 5
        factors.append("+5 has_linkedin")
    else:
        score -= 20
        factors.append("-20 no_linkedin")

    # Has email (direct contact possible)
    if connection.email:
        score += 5
        factors.append("+5 has_email")

    # Conversation history bonus
    if connection.message_count and connection.message_count > 0:
        score += 10
        factors.append("+10 has_messages")

    # Engagement-based boosts
    if connection.engagement_score is not None:
        if connection.engagement_score >= 70:
            score += 25
            factors.append("+25 high_engagement")
        elif connection.engagement_score >= 40:
            score += 15
            factors.append("+15 moderate_engagement")
        elif connection.engagement_score > 0:
            score += 8
            factors.append("+8 some_engagement")

    # Relationship signal boosts
    if connection.has_recommendation:
        score += 20
        factors.append("+20 has_recommendation")
    elif connection.endorsement_count >= 3:
        score += 10
        factors.append("+10 multiple_endorsements")
    elif connection.endorsement_count > 0:
        score += 5
        factors.append("+5 has_endorsement")

    # Clamp score
    score = max(0, min(100, score))

    # Determine tier
    if score >= 70:
        tier = 1  # Enrich
    elif score >= 40:
        tier = 2  # Maybe
    else:
        tier = 3  # Skip

    return PreScoreResult(score=score, tier=tier, factors=factors)


def batch_prescore_llm(
    connections: list[Connection],
    user_profile: UserProfile,
    batch_size: int = 50,
) -> list[tuple[str, float, int]]:
    """
    Batch LLM pre-scoring for more accurate prioritization.

    Sends batches of contacts (name + title + company only) for
    efficient evaluation without full enrichment data.

    Args:
        connections: List of connections to score
        user_profile: User profile for context
        batch_size: How many to process per LLM call

    Returns:
        List of (connection_id, score, tier) tuples
    """
    if not settings.openai_api_key:
        return []

    client = OpenAI(api_key=settings.openai_api_key)
    results = []

    # Build user context
    user_context = f"""User Profile:
- Role: {user_profile.current_role or 'Not specified'}
- Company: {user_profile.company or 'Not specified'}
- Industry: {user_profile.industry or 'Not specified'}
- Goals: {user_profile.goals or 'General networking'}"""

    for i in range(0, len(connections), batch_size):
        batch = connections[i:i + batch_size]

        # Build contacts list
        contacts_text = []
        for j, conn in enumerate(batch):
            contacts_text.append(
                f"{j+1}. {conn.name} | {conn.current_role or 'Unknown'} | {conn.current_company or 'Unknown'}"
            )

        prompt = f"""{user_context}

Score these contacts 0-100 based on potential networking value for this user.
Consider: relevance to goals, seniority/influence, industry alignment, network value.

Contacts:
{chr(10).join(contacts_text)}

Return JSON array with scores:
{{"scores": [{{"index": 1, "score": 75}}, {{"index": 2, "score": 45}}, ...]}}

Be selective - most contacts should score 30-60. Reserve 80+ for exceptional matches."""

        try:
            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            data = json.loads(response.choices[0].message.content)

            for item in data.get("scores", []):
                idx = item.get("index", 0) - 1  # Convert to 0-indexed
                if 0 <= idx < len(batch):
                    score = float(item.get("score", 50))
                    score = max(0, min(100, score))
                    tier = 1 if score >= 70 else (2 if score >= 40 else 3)
                    results.append((batch[idx].id, score, tier))

        except Exception as e:
            print(f"LLM prescore batch error: {e}")
            # Fall back to rule-based for this batch
            for conn in batch:
                rule_result = rule_based_prescore(conn, user_profile)
                results.append((conn.id, rule_result.score, rule_result.tier))

    return results


def prescore_unscored_connections(
    use_llm: bool = True,
    limit: Optional[int] = None,
) -> dict:
    """
    Pre-score all connections that haven't been pre-scored yet.

    Args:
        use_llm: Whether to use LLM batch scoring (more accurate but costs)
        limit: Max number to process (None = all)

    Returns:
        Dict with counts: {"scored": N, "tier1": N, "tier2": N, "tier3": N}
    """
    stats = {"scored": 0, "tier1": 0, "tier2": 0, "tier3": 0}

    with get_session() as session:
        # Get unscored connections
        query = select(Connection).where(Connection.pre_score.is_(None))
        if limit:
            query = query.limit(limit)
        connections = list(session.exec(query).all())

        if not connections:
            return stats

        user_profile = session.get(UserProfile, 1)

        if use_llm and settings.openai_api_key and user_profile:
            # Batch LLM scoring
            results = batch_prescore_llm(
                connections,
                user_profile,
                batch_size=settings.prescore_batch_size,
            )

            for conn_id, score, tier in results:
                conn = session.get(Connection, conn_id)
                if conn:
                    conn.pre_score = score
                    conn.pre_score_tier = tier
                    conn.pre_scored_at = datetime.utcnow()
                    session.add(conn)

                    stats["scored"] += 1
                    stats[f"tier{tier}"] += 1

        else:
            # Rule-based only
            for conn in connections:
                result = rule_based_prescore(conn, user_profile)
                conn.pre_score = result.score
                conn.pre_score_tier = result.tier
                conn.pre_scored_at = datetime.utcnow()
                session.add(conn)

                stats["scored"] += 1
                stats[f"tier{result.tier}"] += 1

    return stats


def get_tier1_connections(limit: int = 10) -> list[Connection]:
    """
    Get top pre-scored connections ready for enrichment.

    Args:
        limit: Max number to return

    Returns:
        List of tier-1 connections sorted by pre_score descending
    """
    with get_session() as session:
        connections = session.exec(
            select(Connection)
            .where(Connection.pre_score_tier == 1)
            .where(Connection.enriched_at.is_(None))  # Not yet enriched
            .where(Connection.linkedin_url.isnot(None))  # Has LinkedIn URL
            .order_by(Connection.pre_score.desc())
            .limit(limit)
        ).all()

        # Detach from session
        result = []
        for conn in connections:
            _ = conn.id, conn.name, conn.pre_score
            result.append(conn)

        return result
