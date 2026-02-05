"""Profile inference from LinkedIn data for Reconnect.

Analyzes LinkedIn dump data to infer user profile attributes like
seniority, industry, expertise, and interests.
"""

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.database.engine import get_session
from src.database.models import UserProfile
from src.ingestion.linkedin_dump import (
    ExtractedDump,
    get_column_value,
    parse_linkedin_date,
)

import csv


# Seniority patterns
SENIORITY_PATTERNS = {
    "executive": [
        r"\b(ceo|cto|cfo|coo|cmo|cpo|ciso)\b",
        r"\bchief\b.*\bofficer\b",
        r"\bpresident\b",
        r"\bfounder\b",
        r"\bco-founder\b",
        r"\bpartner\b",
        r"\bmanaging\s+director\b",
    ],
    "senior": [
        r"\bvp\b",
        r"\bvice\s+president\b",
        r"\bdirector\b",
        r"\bhead\s+of\b",
        r"\bprincipal\b",
        r"\bstaff\b",
        r"\bsenior\s+manager\b",
    ],
    "mid": [
        r"\bmanager\b",
        r"\blead\b",
        r"\bsenior\b",
        r"\bsr\.\b",
    ],
    "entry": [
        r"\bassociate\b",
        r"\bjunior\b",
        r"\bintern\b",
        r"\banalyst\b",
        r"\bcoordinator\b",
        r"\bstudent\b",
    ],
}


def infer_seniority(title: str) -> Optional[str]:
    """
    Infer seniority level from job title.

    Args:
        title: Job title string

    Returns:
        Seniority level: "executive", "senior", "mid", "entry", or None
    """
    if not title:
        return None

    title_lower = title.lower()

    # Check patterns in order of seniority
    for level in ["executive", "senior", "mid", "entry"]:
        for pattern in SENIORITY_PATTERNS[level]:
            if re.search(pattern, title_lower):
                return level

    return None


def extract_expertise_from_title(title: str) -> list[str]:
    """
    Extract expertise areas from job title.

    Args:
        title: Job title string

    Returns:
        List of expertise keywords
    """
    if not title:
        return []

    expertise = []
    title_lower = title.lower()

    # Function/role keywords
    role_keywords = {
        "engineering": ["engineer", "engineering", "developer", "development"],
        "product": ["product"],
        "design": ["design", "ux", "ui"],
        "marketing": ["marketing", "growth"],
        "sales": ["sales", "business development", "account"],
        "operations": ["operations", "ops"],
        "finance": ["finance", "financial", "accounting"],
        "hr": ["hr", "human resources", "people", "talent"],
        "data": ["data", "analytics", "ml", "ai", "machine learning"],
        "security": ["security", "infosec", "cyber"],
    }

    for area, keywords in role_keywords.items():
        if any(kw in title_lower for kw in keywords):
            expertise.append(area)

    return expertise


def infer_industry_from_companies(companies: list[str]) -> Optional[str]:
    """
    Infer likely industry from company names.

    Args:
        companies: List of company names

    Returns:
        Most likely industry or None
    """
    if not companies:
        return None

    # Common industry indicators in company names
    industry_keywords = {
        "technology": ["tech", "software", "app", "digital", "labs", "ai"],
        "finance": ["bank", "capital", "invest", "financial", "fund", "venture"],
        "healthcare": ["health", "medical", "pharma", "bio", "clinic"],
        "consulting": ["consult", "advisory", "partners"],
        "retail": ["retail", "shop", "store", "commerce"],
        "media": ["media", "news", "entertainment", "studio"],
    }

    industry_counts = Counter()

    for company in companies:
        company_lower = company.lower()
        for industry, keywords in industry_keywords.items():
            if any(kw in company_lower for kw in keywords):
                industry_counts[industry] += 1

    if industry_counts:
        return industry_counts.most_common(1)[0][0]

    return None


def extract_interests_from_reactions(reactions_path: Path) -> list[str]:
    """
    Extract interest topics from LinkedIn reactions/likes.

    Args:
        reactions_path: Path to reactions CSV

    Returns:
        List of inferred interest topics
    """
    if not reactions_path or not reactions_path.exists():
        return []

    topic_keywords = []

    try:
        with open(reactions_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # LinkedIn reactions CSV typically has post content or URL
                content = get_column_value(row, "Content", "Post", "Link")
                if content:
                    # Extract meaningful words
                    words = re.findall(r"\b[a-zA-Z]{4,}\b", content.lower())
                    topic_keywords.extend(words)
    except Exception:
        pass

    # Count and filter meaningful topics
    if not topic_keywords:
        return []

    # Common stopwords to filter
    stopwords = {
        "that", "this", "with", "from", "have", "been", "were", "will",
        "your", "what", "when", "where", "which", "their", "about",
        "would", "could", "should", "more", "than", "they", "some",
    }

    word_counts = Counter(w for w in topic_keywords if w not in stopwords)

    # Return top 10 topics
    return [word for word, _ in word_counts.most_common(10)]


def extract_interests_from_comments(comments_path: Path) -> list[str]:
    """
    Extract interest topics from LinkedIn comments.

    Args:
        comments_path: Path to comments CSV

    Returns:
        List of inferred interest topics
    """
    if not comments_path or not comments_path.exists():
        return []

    topics = []

    try:
        with open(comments_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                content = get_column_value(row, "Message", "Comment", "Content")
                if content and len(content) > 20:
                    # Extract hashtags as explicit interests
                    hashtags = re.findall(r"#(\w+)", content)
                    topics.extend(hashtags)
    except Exception:
        pass

    if topics:
        counts = Counter(t.lower() for t in topics)
        return [t for t, _ in counts.most_common(10)]

    return []


def parse_positions_csv(positions_path: Path) -> list[dict]:
    """
    Parse Positions.csv from LinkedIn export.

    Args:
        positions_path: Path to positions CSV

    Returns:
        List of position dicts with title, company, dates
    """
    if not positions_path or not positions_path.exists():
        return []

    positions = []

    try:
        with open(positions_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = get_column_value(row, "Title", "Position")
                company = get_column_value(row, "Company Name", "Company", "Organization")
                started = get_column_value(row, "Started On", "Start Date")
                ended = get_column_value(row, "Finished On", "End Date")

                if title or company:
                    positions.append({
                        "title": title,
                        "company": company,
                        "started": parse_linkedin_date(started),
                        "ended": parse_linkedin_date(ended),
                    })
    except Exception:
        pass

    # Sort by start date descending (most recent first)
    positions.sort(key=lambda p: p.get("started") or datetime.min, reverse=True)
    return positions


def parse_skills_csv(skills_path: Path) -> list[str]:
    """
    Parse Skills.csv from LinkedIn export.

    Args:
        skills_path: Path to skills CSV

    Returns:
        List of skill names
    """
    if not skills_path or not skills_path.exists():
        return []

    skills = []

    try:
        with open(skills_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                skill = get_column_value(row, "Name", "Skill")
                if skill:
                    skills.append(skill)
    except Exception:
        pass

    return skills


def infer_user_profile_from_dump(dump: ExtractedDump) -> dict:
    """
    Build inferred UserProfile attributes from LinkedIn data.

    Args:
        dump: ExtractedDump with paths to LinkedIn export files

    Returns:
        Dict with inferred profile attributes
    """
    result = {
        "inferred_industry": None,
        "inferred_seniority": None,
        "inferred_expertise": [],
        "inferred_interests": [],
    }

    # Parse positions for career data
    positions = parse_positions_csv(dump.positions_path)

    if positions:
        # Use current/most recent position for seniority
        current = positions[0]
        result["inferred_seniority"] = infer_seniority(current.get("title", ""))

        # Aggregate expertise from all positions
        all_expertise = []
        for pos in positions[:5]:  # Last 5 positions
            all_expertise.extend(extract_expertise_from_title(pos.get("title", "")))
        result["inferred_expertise"] = list(set(all_expertise))

        # Infer industry from companies
        companies = [p.get("company", "") for p in positions if p.get("company")]
        result["inferred_industry"] = infer_industry_from_companies(companies)

    # Add skills to expertise
    skills = parse_skills_csv(dump.skills_path)
    if skills:
        # Combine skills with title-based expertise
        result["inferred_expertise"] = list(set(result["inferred_expertise"] + skills[:20]))

    # Extract interests from engagement
    reaction_interests = extract_interests_from_reactions(dump.reactions_path)
    comment_interests = extract_interests_from_comments(dump.comments_path)
    result["inferred_interests"] = list(set(reaction_interests + comment_interests))[:20]

    return result


def update_user_profile_from_dump(dump: ExtractedDump) -> bool:
    """
    Update UserProfile with inferred data from LinkedIn dump.

    Args:
        dump: ExtractedDump with paths to LinkedIn export files

    Returns:
        True if profile was updated
    """
    inferred = infer_user_profile_from_dump(dump)

    with get_session() as session:
        profile = session.get(UserProfile, 1)
        if not profile:
            # Create profile if it doesn't exist
            profile = UserProfile(id=1, name="")

        # Update inferred fields
        profile.inferred_industry = inferred["inferred_industry"]
        profile.inferred_seniority = inferred["inferred_seniority"]
        profile.inferred_expertise = inferred["inferred_expertise"]
        profile.inferred_interests = inferred["inferred_interests"]
        profile.profile_auto_updated_at = datetime.utcnow()

        # Also update main profile fields if empty
        if not profile.industry and inferred["inferred_industry"]:
            profile.industry = inferred["inferred_industry"]

        session.add(profile)

    return True
