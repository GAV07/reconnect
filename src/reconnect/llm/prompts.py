"""Prompt templates for LLM integration."""

SYSTEM_PROMPT = """You are an expert at professional networking and relationship building.
You help people reconnect with their contacts in authentic, non-salesy ways.
Focus on genuine shared interests, mutual value, and natural conversation starters.
Never suggest reaching out just to "catch up" without a specific hook.
Always respond with valid JSON."""


def build_prose_prompt(
    user_context: str,
    contact_name: str,
    current_role: str,
    current_company: str,
    headline: str,
    skills: list[str],
    career_trajectory: str,
    activity_text: str,
) -> str:
    """Build the prompt for generating outreach prose."""
    skills_str = ", ".join(skills[:5]) if skills else "N/A"

    return f"""You are helping me reconnect with a professional contact. Generate personalized outreach content.

{user_context}
CONTACT INFORMATION:
- Name: {contact_name}
- Current role: {current_role}
- Company: {current_company}
- Headline: {headline}
- Key skills: {skills_str}{career_trajectory}

RECENT LINKEDIN ACTIVITY:
{activity_text}

TASK:
Based on the above, generate:
1. A 2-sentence summary of their current career status and recent focus areas
2. A specific, genuine reason to reach out (based on their activity or career move, NOT generic)
3. A warm, personalized opening message (3-4 sentences, casual professional tone)
4. 2-3 talking points for the conversation

Respond in JSON format:
{{
  "summary": "...",
  "reason_to_reach_out": "...",
  "suggested_message": "...",
  "talking_points": ["...", "...", "..."]
}}"""


def format_user_context(
    name: str = "",
    current_role: str = "",
    company: str = "",
    industry: str = "",
    goals: str = "",
    interests: str = "",
) -> str:
    """Format user profile into prompt context."""
    if not any([name, current_role, company, goals]):
        return ""

    return f"""MY BACKGROUND:
- Name: {name or 'Not specified'}
- Current role: {current_role or 'Not specified'}
- Company: {company or 'Not specified'}
- Industry: {industry or 'Not specified'}
- Goals: {goals or 'Reconnecting with my network'}
- Interests: {interests or 'Not specified'}
"""
