"""Generate rich searchable profile text from contact enrichment data.

Concatenates all useful fields into a single text blob optimized for
embedding-based semantic search. The text is structured so that an
embedding model can capture: identity, role, company, industry, skills,
education, location, career trajectory, and interests/activity.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.database.models import Connection


def build_profile_text(connection: "Connection") -> str:
    """Build a searchable text profile from a connection's data.

    Returns empty string if there's not enough data to be useful.
    """
    from src.database.models import get_enrichment_data

    parts: list[str] = []

    # Name
    if connection.name:
        parts.append(connection.name)

    # Current role and company
    role_line = _build_role_line(connection)
    if role_line:
        parts.append(role_line)

    # Headline (often contains self-description)
    if connection.enriched_headline:
        parts.append(connection.enriched_headline)

    # Industry
    if connection.enriched_industry:
        parts.append(f"Industry: {connection.enriched_industry}")

    # Location
    location_parts = []
    if connection.enriched_city:
        location_parts.append(connection.enriched_city)
    if connection.enriched_country:
        location_parts.append(connection.enriched_country)
    if location_parts:
        parts.append(f"Location: {', '.join(location_parts)}")
    elif connection.location:
        parts.append(f"Location: {connection.location}")

    # Seniority
    if connection.enriched_seniority:
        parts.append(f"Seniority: {connection.enriched_seniority}")

    # Now dig into raw enrichment for richer data
    data = get_enrichment_data(connection)
    if data:
        # About / bio
        about = data.get("about") or data.get("summary") or ""
        if about:
            parts.append(about[:500])

        # Skills
        skills = _extract_skills(data)
        if skills:
            parts.append(f"Skills: {', '.join(skills)}")

        # Career history
        career = _extract_career_history(data)
        if career:
            parts.append(f"Career: {career}")

        # Education
        education = _extract_education(data)
        if education:
            parts.append(f"Education: {education}")

        # Languages
        languages = _extract_languages(data)
        if languages:
            parts.append(f"Languages: {languages}")

        # Company details
        company_detail = _extract_company_detail(data)
        if company_detail:
            parts.append(company_detail)

    # Activity / posts (shows interests and thought leadership)
    if connection.activity_log:
        activity_text = _extract_activity_text(connection.activity_log)
        if activity_text:
            parts.append(f"Posts about: {activity_text}")

    # Conversation context
    if connection.conversation_summary:
        parts.append(f"Conversation: {connection.conversation_summary[:200]}")

    # Tags
    if connection.tags:
        parts.append(f"Tags: {connection.tags}")

    # Notes
    if connection.notes:
        parts.append(f"Notes: {connection.notes[:200]}")

    text = "\n".join(parts)
    # Only return if we have meaningful content beyond just a name
    return text if len(parts) >= 3 else ""


def _build_role_line(connection: "Connection") -> str:
    role = connection.current_role or ""
    company = connection.current_company or ""
    if role and company:
        return f"{role} at {company}"
    return role or company


def _extract_skills(data: dict) -> list[str]:
    skills_raw = data.get("skills") or []
    if not isinstance(skills_raw, list):
        return []
    skills = []
    for s in skills_raw[:15]:
        if isinstance(s, dict):
            name = s.get("title") or s.get("name") or ""
        else:
            name = str(s)
        if name:
            skills.append(name)
    return skills


def _extract_career_history(data: dict) -> str:
    experiences = data.get("experiences") or []
    if not isinstance(experiences, list):
        return ""
    lines = []
    for exp in experiences[:6]:
        if not isinstance(exp, dict):
            continue
        title = exp.get("title") or exp.get("jobTitle") or ""
        company = exp.get("company") or exp.get("companyName") or ""
        industry = exp.get("companyIndustry") or ""
        if title and company:
            line = f"{title} at {company}"
            if industry:
                line += f" ({industry})"
            lines.append(line)
    return "; ".join(lines)


def _extract_education(data: dict) -> str:
    educations = data.get("educations") or []
    if not isinstance(educations, list):
        return ""
    lines = []
    for edu in educations[:4]:
        if not isinstance(edu, dict):
            continue
        school = edu.get("school") or edu.get("schoolName") or ""
        degree = edu.get("degree") or ""
        field = edu.get("fieldOfStudy") or edu.get("field") or ""
        if school:
            line = school
            if degree or field:
                line += f" - {degree} {field}".strip()
            lines.append(line)
    return "; ".join(lines)


def _extract_languages(data: dict) -> str:
    languages = data.get("languages") or []
    if not isinstance(languages, list):
        return ""
    names = []
    for lang in languages[:5]:
        if isinstance(lang, dict):
            name = lang.get("name") or ""
        else:
            name = str(lang)
        if name:
            names.append(name)
    return ", ".join(names)


def _extract_company_detail(data: dict) -> str:
    parts = []
    size = data.get("companySize") or data.get("company_size") or ""
    if size:
        parts.append(f"Company size: {size}")
    website = data.get("companyWebsite") or data.get("company_website") or ""
    if website:
        parts.append(f"Company website: {website}")
    return "; ".join(parts)


def _extract_activity_text(activity_log: list) -> str:
    """Extract a summary of what the person posts about."""
    texts = []
    for post in activity_log[:5]:
        if isinstance(post, dict):
            content = post.get("content") or ""
            if content:
                texts.append(content[:150])
    return " | ".join(texts) if texts else ""
