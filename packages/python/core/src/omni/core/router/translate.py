"""
LLM layer for router: query translation and catalog enrichment.

The pipeline uses a common language (English) for routing; we do not know what
language the user will use. This layer is always part of the search pipeline:
(1) translate non-English queries to English (default on), (2) optionally
enrich attribute values at index time. Both steps use the LLM only.

1. Query translation (non-English → English) — default on
   Translation is enabled by default (router.translation.enabled: true). Set
   false only when all queries are known to be English.

2. Catalog enrichment (diversify attribute values)
   Optional at index time: router.enrichment.enabled. Expands routing_keywords
   with synonyms/related terms to strengthen the search mechanism.
"""

from __future__ import annotations

import re
from omni.foundation.config.logging import get_logger
from omni.foundation.config.settings import get_setting

logger = get_logger("omni.core.router.translate")

_TRANSLATE_SYSTEM = """You are a translator. You must respond in English only. Do not output Chinese or any other language.

Task: Output exactly one short line — the English translation of the user's message. Keep URLs and paths unchanged.

Examples:
- "帮我研究一下 https://example.com/repo" -> "Help me research https://example.com/repo"
- "分析这个仓库" -> "Analyze this repository"
- "git commit" -> "git commit"

Rules: One line only. English only. No explanation, no title, no #."""


def _is_likely_english(text: str) -> bool:
    """Heuristic: treat as English only if the non-URL part is mostly ASCII letters."""
    # Strip URLs and paths so we don't count them
    cleaned = re.sub(r"https?://\S+", " ", text)
    cleaned = re.sub(r"[A-Za-z0-9_.-]+\.(ncl|py|json|yaml|md)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    if not cleaned:
        return True
    # If any non-ASCII character (e.g. CJK) appears, treat as non-English so we translate
    if any(ord(c) > 127 for c in cleaned):
        return False
    # Otherwise check that most token chars are ASCII letters
    tokens = re.findall(r"[A-Za-z]+", cleaned)
    if not tokens:
        return True
    ascii_word = sum(1 for t in tokens if t.isascii() and t.isalpha())
    return (ascii_word / len(tokens)) >= 0.5


async def translate_query_to_english(
    query: str,
    *,
    enabled: bool | None = None,
    model: str | None = None,
    fallback_to_original: bool = True,
) -> str:
    """Translate a user query to English for routing (keyword match uses English only).

    When router.translation.enabled is True, non-English queries are translated
    via the configured LLM (e.g. Pangu, MiniMax). SKILL.md content is English-only,
    so the keyword branch needs an English query to match routing_keywords.

    Args:
        query: Raw user query (any language).
        enabled: Override config; if None, uses get_setting("router.translation.enabled", False).
        model: Override translation model; if None, uses router.translation.model or inference.model.
        fallback_to_original: If True, on failure or when disabled, return query unchanged.

    Returns:
        English query string to use for embedding and keyword search, or original on failure/disabled.
    """
    if not query or not query.strip():
        return query

    if enabled is None:
        enabled = bool(get_setting("router.translation.enabled", True))
    if not enabled:
        return query

    if _is_likely_english(query):
        return query

    if model is None:
        model = get_setting("router.translation.model", None) or get_setting(
            "inference.model", None
        )

    try:
        from omni.foundation.services.llm.provider import get_llm_provider

        provider = get_llm_provider()
        if not provider.is_available():
            logger.debug("Translation skipped: LLM provider not available")
            return query if fallback_to_original else query

        out = await provider.complete_async(
            _TRANSLATE_SYSTEM,
            user_query=query.strip(),
            model=model,
            max_tokens=512,
        )
        if out and isinstance(out, str) and out.strip():
            translated = out.strip().split("\n")[0].strip()
            if translated.startswith("# "):
                translated = translated[2:].strip()
            if translated and not any(ord(c) > 127 for c in translated):
                logger.debug(
                    "Query translated for routing",
                    original_preview=query[:50],
                    translated_preview=translated[:50],
                )
                return translated
            if translated and any(ord(c) > 127 for c in translated):
                logger.debug(
                    "Translation still non-English, using fallback",
                    translated_preview=translated[:50],
                )
    except Exception as e:
        logger.warning("Query translation failed, using original", error=str(e))

    fallback = _routing_fallback_for_non_english(query)
    if fallback:
        return fallback
    return query if fallback_to_original else query


def _routing_fallback_for_non_english(query: str) -> str | None:
    """When LLM translation fails or returns non-English, build a minimal English phrase for routing.
    Used only as fallback after LLM attempt; no language-specific keywords.
    """
    url_match = re.search(r"https?://[^\s]+", query)
    if url_match:
        return "research " + url_match.group(0).strip()
    return None


_ENRICH_KEYWORDS_SYSTEM = """You are a search-indexing assistant. Given a tool's short description and its existing routing keywords, suggest additional English keywords or short phrases that users might type when looking for this tool.
Rules:
- Output only a single line: comma-separated additional keywords/phrases (no numbering, no explanation).
- Prefer synonyms, related verbs/nouns, and common alternate phrasings. Keep each token short (1-3 words).
- Do not repeat the existing keywords. Do not include the description verbatim.
- If there is nothing useful to add, output a single dash: -"""


async def enrich_routing_keywords(
    description: str,
    routing_keywords: list[str],
    *,
    enabled: bool | None = None,
    model: str | None = None,
) -> list[str]:
    """Use the LLM to suggest additional keywords for indexing (synonyms, related terms).

    Merging the result with the original routing_keywords gives more diverse
    attribute values in the index so that keyword search matches more user phrasings.

    Args:
        description: Tool/skill description (English).
        routing_keywords: Existing routing_keywords from SKILL.md.
        enabled: Override config; if None, uses router.enrichment.enabled.
        model: Override model; if None, uses router.enrichment.model or inference.model.

    Returns:
        Additional keywords/phrases to merge with routing_keywords (may be empty).
    """
    if enabled is None:
        enabled = bool(get_setting("router.enrichment.enabled", False))
    if not enabled or not description:
        return []

    if model is None:
        model = get_setting("router.enrichment.model", None) or get_setting("inference.model", None)

    expand = bool(get_setting("router.enrichment.expand_keywords", True))
    if not expand:
        return []

    try:
        from omni.foundation.services.llm.provider import get_llm_provider

        provider = get_llm_provider()
        if not provider.is_available():
            return []

        user = f"Description: {description[:400]}\nExisting keywords: {', '.join(routing_keywords[:30])}"
        out = await provider.complete_async(
            _ENRICH_KEYWORDS_SYSTEM,
            user_query=user,
            model=model,
            max_tokens=256,
        )
        if not out or not isinstance(out, str) or not out.strip():
            return []
        line = out.strip().split("\n")[0].strip()
        if not line or line == "-":
            return []
        # Parse comma-separated tokens; normalize
        extra = [t.strip().lower() for t in line.split(",") if t.strip() and t.strip() != "-"]
        # Dedupe and exclude already present
        existing_lower = {k.lower() for k in routing_keywords}
        return [t for t in extra if t and t not in existing_lower][:20]
    except Exception as e:
        logger.debug("Enrichment skipped or failed", error=str(e))
        return []
