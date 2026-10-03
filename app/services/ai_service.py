import logging
from functools import lru_cache

from openai import OpenAI, OpenAIError

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_DIRECT_CHARS = 12_000  # above this, summarise in chunks
CHUNK_CHARS = 10_000
MAX_CHUNKS = 6  # hard cap to bound cost on very large documents

SUMMARY_SYSTEM = (
    "You are an educational assistant. Summarise the learning material given by the user. "
    "Use ONLY information found in the material and do not add outside facts. "
    "Write Markdown with exactly these sections: "
    "'## Overview' (2-3 sentences), "
    "'## Key Concepts' (bullet list, each with a one-line explanation), "
    "'## Key Takeaways' (3-5 bullets)."
)
CHUNK_SYSTEM = (
    "Summarise this part of a longer document as a concise bullet list. "
    "Use only the text provided."
)


class AIServiceError(Exception):
    """Raised when the AI provider is not configured or the request fails."""


@lru_cache(maxsize=1)
def _get_client() -> OpenAI:
    if not settings.ai_api_key:
        raise AIServiceError("AI_API_KEY is not configured on the server.")
    return OpenAI(
        api_key=settings.ai_api_key, base_url=settings.ai_base_url, timeout=60
    )


def chat(system: str, user: str) -> str:
    """Single LLM call. All provider errors are converted to AIServiceError."""
    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=settings.ai_model,
            temperature=0.3,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    except OpenAIError as exc:
        logger.exception("AI provider request failed")
        raise AIServiceError("The AI provider request failed. Try again later.") from exc
    content = response.choices[0].message.content
    if not content:
        raise AIServiceError("The AI provider returned an empty response.")
    return content.strip()


def _split_chunks(text: str) -> list[str]:
    chunks = [text[i : i + CHUNK_CHARS] for i in range(0, len(text), CHUNK_CHARS)]
    if len(chunks) > MAX_CHUNKS:  # keep evenly spaced chunks across the document
        step = len(chunks) / MAX_CHUNKS
        chunks = [chunks[int(i * step)] for i in range(MAX_CHUNKS)]
    return chunks


def summarize(text: str) -> str:
    if len(text) <= MAX_DIRECT_CHARS:
        return chat(SUMMARY_SYSTEM, text)
    partials = [chat(CHUNK_SYSTEM, chunk) for chunk in _split_chunks(text)]
    return chat(SUMMARY_SYSTEM, "\n\n".join(partials))
