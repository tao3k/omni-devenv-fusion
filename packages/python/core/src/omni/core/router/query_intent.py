"""
query_intent.py - Rule-based and optional LLM-driven intent classification for agentic tool search.

Aligns with:
- docs/testing/router-file-discovery-intent-report.md
- packages/rust/crates/omni-vector/src/keyword/fusion.rs (is_file_discovery_query)

Classifies the user query into intent (exact | semantic | hybrid) and optional
category_filter (e.g. file_discovery) so the router can call agentic_search
with the right strategy and filters.

When router.intent.use_llm is True, intent can be computed by LLM; otherwise
rule-based classification is used (default).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.router.query_intent")

# Tool ID pattern aligned with hybrid_search._TOOL_ID_RE (skill.command format).
_TOOL_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,160}$")

# Minimum length to treat as a possible exact command (avoid single letters).
_MIN_EXACT_LEN = 3
# Max length for exact (long strings are likely natural language).
_MAX_EXACT_LEN = 80

# File-discovery intent terms (same as Rust fusion.rs is_file_discovery_query).
# Use advanced_tools.smart_find when query matches these; category_filter="file_discovery".
_FILE_DISCOVERY_TERMS = frozenset(
    {
        "find",
        "list",
        "files",
        "file",
        "directory",
        "folder",
        "path",
        "glob",
        "extension",
    }
)


@dataclass(frozen=True)
class ToolSearchIntentResult:
    """Result of intent classification for tool search.

    intent: Strategy for Rust agentic_search ("exact" | "semantic" | "hybrid").
    category_filter: Optional category to restrict results (e.g. "file_discovery").
    """

    intent: str
    category_filter: str | None = None


def _normalize_query_parts(query: str) -> list[str]:
    """Tokenize query for term matching (alphanumeric tokens, lowercased)."""
    q = query.strip().lower()
    return re.findall(r"[a-z0-9*]+", q)


# Terms that suggest "list/find tools or capabilities" (skill.discover / list_tools resource), not files.
_TOOL_CAPABILITY_TERMS = frozenset(
    {
        "tools",
        "commands",
        "capability",
        "capabilities",
        "skill",
        "skills",
        "available",
        "omni",
        "registry",
    }
)


def _is_file_discovery_query(query: str) -> bool:
    """True if query is about locating files/directories (same logic as Rust fusion.rs)."""
    q_lower = query.strip().lower()
    parts = _normalize_query_parts(query)
    # If query clearly asks for tools/capabilities (e.g. "list available tools"), do not treat as file_discovery.
    if _TOOL_CAPABILITY_TERMS.intersection(parts) and any(
        p in _FILE_DISCOVERY_TERMS for p in parts
    ):
        return False
    if any(part in _FILE_DISCOVERY_TERMS for part in parts):
        return True
    if any(part.startswith("*.") for part in parts):
        return True
    if ".py" in q_lower or ".rs" in q_lower:
        return True
    return False


def classify_tool_search_intent(query: str) -> str:
    """Classify query for agentic search strategy (backward-compatible: returns intent only).

    - exact: Query looks like a single tool id (e.g. "git.commit", "knowledge.recall").
      Uses keyword-only path when store has keyword index for faster exact match.
    - hybrid: Natural language or multi-word query. Uses full vector + keyword RRF.

    Args:
        query: Raw user query (e.g. "git commit", "knowledge.recall").

    Returns:
        "exact" or "hybrid".
    """
    return classify_tool_search_intent_full(query).intent


def classify_tool_search_intent_full(query: str) -> ToolSearchIntentResult:
    """Classify query into intent and optional category_filter (sample-aligned with report + Rust).

    Uses the same file-discovery rules as:
    - docs/testing/router-file-discovery-intent-report.md
    - packages/rust/crates/omni-vector/src/keyword/fusion.rs (is_file_discovery_query)

    Intent strategy:
    - exact: Single token, skill.command pattern → keyword-only when query_text set.
    - semantic: Reserved for future (e.g. "what is", "explain") → vector-only; currently falls to hybrid.
    - hybrid: Default; full vector + keyword RRF.

    Category filter:
    - file_discovery: When normalized terms include find/list/file(s)/directory/folder/path/glob/extension
      or *.py / *.rs → prefer tools with category file_discovery (e.g. advanced_tools.smart_find).

    Args:
        query: Raw user query (e.g. "find *.py files", "git commit", "list directory").

    Returns:
        ToolSearchIntentResult with intent and optional category_filter.
    """
    if not query or not isinstance(query, str):
        return ToolSearchIntentResult("hybrid", None)

    q = query.strip()
    if len(q) < _MIN_EXACT_LEN or len(q) > _MAX_EXACT_LEN:
        intent = "hybrid"
        category_filter = "file_discovery" if _is_file_discovery_query(q) else None
        return ToolSearchIntentResult(intent, category_filter)

    # Exact: single token, skill.command pattern
    if " " in q:
        intent = "hybrid"
        category_filter = "file_discovery" if _is_file_discovery_query(q) else None
        return ToolSearchIntentResult(intent, category_filter)
    if not _TOOL_ID_RE.match(q) or "." not in q or not any(c.isalpha() for c in q):
        intent = "hybrid"
        category_filter = "file_discovery" if _is_file_discovery_query(q) else None
        return ToolSearchIntentResult(intent, category_filter)

    return ToolSearchIntentResult("exact", None)


# ---------------------------------------------------------------------------
# Optional LLM-driven intent classification (P2 Agentic enhancement)
# ---------------------------------------------------------------------------

_INTENT_LLM_SYSTEM = """You classify the user's search intent for a tool/skill router.

Output exactly one JSON object with two keys:
- "intent": one of "exact", "semantic", "hybrid"
  - exact: user typed a single tool id like "git.commit" or "knowledge.recall"
  - semantic: user wants conceptual similarity (e.g. "explain", "what is") — use vector-only
  - hybrid: natural language or multi-word query — use vector + keyword fusion
- "category_filter": null, or "file_discovery" when the query is about finding/listing files (find files, list directory, glob *.py, etc.)

Rules: One JSON line only. No markdown, no explanation. If unsure, use "hybrid" and null."""


_VALID_INTENTS = frozenset({"exact", "semantic", "hybrid"})
_VALID_CATEGORY_FILTERS = frozenset({None, "file_discovery"})


async def classify_tool_search_intent_with_llm(
    query: str,
    *,
    enabled: bool | None = None,
    model: str | None = None,
) -> ToolSearchIntentResult | None:
    """Classify query intent using LLM when enabled. Returns None on disabled/failure (caller falls back to rule-based).

    Uses router.intent.use_llm and router.intent.model (or inference.model) when not overridden.

    Args:
        query: Raw user query.
        enabled: Override config; if None, uses get_setting("router.intent.use_llm", False).
        model: Override model; if None, uses router.intent.model or inference.model.

    Returns:
        ToolSearchIntentResult when LLM returns valid intent; None otherwise (use rule-based fallback).
    """
    from omni.foundation.config.settings import get_setting

    if not query or not query.strip():
        return None
    if enabled is None:
        enabled = bool(get_setting("router.intent.use_llm", False))
    if not enabled:
        return None
    if model is None:
        model = get_setting("router.intent.model", None) or get_setting("inference.model", None)

    try:
        from omni.foundation.services.llm.provider import get_llm_provider

        provider = get_llm_provider()
        if not provider.is_available():
            logger.debug("LLM intent skipped: provider not available")
            return None

        out = await provider.complete_async(
            _INTENT_LLM_SYSTEM,
            user_query=query.strip(),
            model=model,
            max_tokens=128,
        )
        if not out or not isinstance(out, str) or not out.strip():
            return None

        raw = out.strip()
        # Strip markdown code block if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0].strip()
        raw = raw.strip()

        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        intent = (parsed.get("intent") or "hybrid").strip().lower()
        if intent not in _VALID_INTENTS:
            intent = "hybrid"
        cat = parsed.get("category_filter")
        if cat is not None:
            cat = str(cat).strip().lower() if cat else None
        if cat and cat != "file_discovery":
            cat = None
        logger.debug(
            "LLM intent classification",
            intent=intent,
            category_filter=cat,
            query_preview=query[:40],
        )
        return ToolSearchIntentResult(intent, cat or None)
    except Exception as e:
        logger.debug("LLM intent classification failed, using rule-based fallback", error=str(e))
        return None
