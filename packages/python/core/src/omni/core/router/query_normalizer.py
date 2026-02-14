"""
Query normalizer for router: optional typo map from config and URL placeholder.

- Typo correction is config-only (router.normalize.typos). No built-in typo list;
  for robust typo/paraphrase handling use the model + semantic search or model + XML
  Q&A–style normalization instead of expanding a static map.
- URL replacement (long URLs → short tokens) keeps intent terms from being diluted
  in embedding/keyword search.
"""

from __future__ import annotations

import re

from omni.foundation.config.settings import get_setting


def _get_typo_map() -> dict[str, str]:
    """Typo map from config only (router.normalize.typos). Empty if unset."""
    custom = get_setting("router.normalize.typos") or {}
    if isinstance(custom, dict):
        return {str(k).strip().lower(): str(v).strip() for k, v in custom.items() if k and v}
    return {}


def normalize_for_routing(query: str) -> str:
    """Normalize query for routing.

    - Applies typo corrections only when router.normalize.typos is set (config-driven).
    - Replaces long URLs with short tokens ('url', 'github url') so intent terms
      are not diluted in embedding/keyword.

    Args:
        query: Raw user query.

    Returns:
        Normalized string for embedding and keyword search.
    """
    stripped = query.strip() if query else ""
    if not stripped:
        return stripped if query is not None else ""

    text = stripped

    # Typo correction from config + built-in (word-boundary, case-insensitive)
    typo_map = _get_typo_map()
    for typo, correct in typo_map.items():
        pattern = r"\b" + re.escape(typo) + r"\b"
        text = re.sub(pattern, correct, text, flags=re.IGNORECASE)

    # Replace URL(s) with short tokens so intent terms get more weight
    url_pattern = re.compile(r"https?://[^\s]+")
    if url_pattern.search(text):
        # Prefer "github url" when it's a GitHub link so "github" keyword matches
        def replace_url(m: re.Match[str]) -> str:
            url = m.group(0)
            if "github" in url.lower():
                return " github url "
            return " url "

        text = url_pattern.sub(replace_url, text)
        text = re.sub(r"\s+", " ", text).strip()

    return text
