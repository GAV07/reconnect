"""Generate and store OpenAI embeddings for contact profile text.

Uses text-embedding-3-small (1536 dimensions) to create vector
representations of profile_text for semantic search.
"""

import json
import logging
from datetime import datetime

import requests as http_requests
from sqlmodel import select

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection
from src.pipeline.profile_text import build_profile_text

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
BATCH_SIZE = 50  # OpenAI supports up to 2048 inputs per request


def generate_embeddings(force: bool = False) -> dict:
    """Generate profile text and embeddings for all contacts that need them.

    Args:
        force: If True, regenerate for all contacts. If False, only missing.

    Returns:
        {"profile_texts_generated": N, "embeddings_generated": N, "errors": N}
    """
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not set, skipping embedding generation")
        return {"profile_texts_generated": 0, "embeddings_generated": 0, "errors": 0}

    stats = {"profile_texts_generated": 0, "embeddings_generated": 0, "errors": 0}

    with get_session() as session:
        # Step 1: Generate profile_text for contacts that need it
        if force:
            candidates = session.exec(select(Connection)).all()
        else:
            candidates = session.exec(
                select(Connection).where(Connection.enriched_at.isnot(None))
            ).all()

        needs_embedding = []
        for conn in candidates:
            text = build_profile_text(conn)
            if text and (force or conn.profile_text != text):
                conn.profile_text = text
                conn.updated_at = datetime.utcnow()
                session.add(conn)
                stats["profile_texts_generated"] += 1
                needs_embedding.append(conn)
            elif text and not force and getattr(conn, "profile_embedding", None) is None:
                needs_embedding.append(conn)

        session.commit()

        # Step 2: Generate embeddings in batches
        for i in range(0, len(needs_embedding), BATCH_SIZE):
            batch = needs_embedding[i : i + BATCH_SIZE]
            texts = [c.profile_text for c in batch if c.profile_text]
            conns = [c for c in batch if c.profile_text]

            if not texts:
                continue

            try:
                embeddings = _call_openai_embeddings(texts)
                for conn, embedding in zip(conns, embeddings):
                    conn.profile_embedding = _format_pgvector(embedding)
                    conn.updated_at = datetime.utcnow()
                    session.add(conn)
                    stats["embeddings_generated"] += 1
                session.commit()
            except Exception as e:
                logger.error(f"Embedding batch failed: {e}")
                stats["errors"] += 1

    logger.info(
        f"Embeddings: {stats['profile_texts_generated']} texts, "
        f"{stats['embeddings_generated']} embeddings, {stats['errors']} errors"
    )
    return stats


def embed_query(text: str) -> list[float]:
    """Embed a single search query. Returns list of floats."""
    result = _call_openai_embeddings([text])
    return result[0]


def _call_openai_embeddings(texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API. Returns list of embedding vectors."""
    response = http_requests.post(
        "https://api.openai.com/v1/embeddings",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": EMBEDDING_MODEL,
            "input": texts,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    # Sort by index to maintain order
    sorted_data = sorted(data["data"], key=lambda x: x["index"])
    return [item["embedding"] for item in sorted_data]


def _format_pgvector(embedding: list[float]) -> str:
    """Format embedding as pgvector string literal for SQLite storage.

    The actual vector format for Supabase is handled during sync.
    For SQLite we store as JSON string.
    """
    return json.dumps(embedding)
