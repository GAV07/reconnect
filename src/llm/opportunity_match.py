"""Opportunity matching — find contacts for specific needs.

Sends batches of contacts to the LLM with an ad-hoc request
(e.g. "intro to someone in edtech") and returns only relevant matches
with scores and reasoning.  Reuses the batch_prescore_llm pattern:
cheap gpt-4o-mini calls, ~50 contacts per batch, JSON response format.
"""

import json
from dataclasses import dataclass

from openai import OpenAI
from sqlmodel import select

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection


MATCH_SYSTEM_PROMPT = (
    "You match professional contacts to specific requests. "
    "Return only genuinely relevant matches. "
    "Always respond with valid JSON."
)


@dataclass
class MatchResult:
    """A single contact that matched an opportunity request."""

    connection_id: str
    name: str
    score: int          # 0-100 relevance to the specific request
    reason: str         # Why this contact matches
    connection: Connection  # full object for UI rendering


def _build_batch_prompt(request: str, batch: list[tuple[int, Connection]]) -> str:
    """Build the user prompt for one batch of contacts."""
    lines = []
    for idx, conn in batch:
        role = conn.current_role or "Unknown role"
        company = conn.current_company or "Unknown company"
        location = conn.location or ""
        parts = [f"{idx}. {conn.name} | {role} @ {company}"]
        if location:
            parts[0] += f" | {location}"
        lines.append(parts[0])

    return f"""Request: {request}

Contacts:
{chr(10).join(lines)}

Return a JSON object with a "matches" array.  Each element must have:
  "index" (int — the contact number above),
  "score" (int 0-100 — relevance to the request),
  "reason" (string — one sentence explaining the match).

Only include contacts with score >= 60.
If no contacts are relevant, return {{"matches": []}}.
"""


def find_matches(
    request: str,
    limit: int = 10,
    batch_size: int = 50,
) -> list[MatchResult]:
    """Find contacts matching a specific opportunity request.

    Args:
        request: Free-text description of what the user is looking for.
        limit: Max results to return (sorted by score desc).
        batch_size: Contacts per LLM call.

    Returns:
        List of MatchResult sorted by score descending.
    """
    if not settings.openai_api_key:
        return []

    # Fetch all contacts that have at least a name + (role or company)
    with get_session() as session:
        candidates = session.exec(
            select(Connection).where(
                (Connection.current_role.isnot(None))
                | (Connection.current_company.isnot(None))
            )
        ).all()

        if not candidates:
            return []

        # Assign a global index so we can map LLM responses back
        indexed: list[tuple[int, Connection]] = [
            (i + 1, c) for i, c in enumerate(candidates)
        ]

        client = OpenAI(api_key=settings.openai_api_key)
        all_matches: list[MatchResult] = []

        for start in range(0, len(indexed), batch_size):
            batch = indexed[start : start + batch_size]
            prompt = _build_batch_prompt(request, batch)

            try:
                response = client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[
                        {"role": "system", "content": MATCH_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=1000,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                )

                data = json.loads(response.choices[0].message.content)

                # Build a quick lookup: global index → Connection
                idx_to_conn = {idx: conn for idx, conn in batch}

                for m in data.get("matches", []):
                    idx = m.get("index")
                    score = m.get("score", 0)
                    reason = m.get("reason", "")
                    conn = idx_to_conn.get(idx)
                    if conn and score >= 60:
                        all_matches.append(
                            MatchResult(
                                connection_id=conn.id,
                                name=conn.name,
                                score=int(score),
                                reason=reason,
                                connection=conn,
                            )
                        )

            except Exception as e:
                print(f"Opportunity match batch error: {e}")
                continue

    # Sort by score descending, take top `limit`
    all_matches.sort(key=lambda m: m.score, reverse=True)
    return all_matches[:limit]
