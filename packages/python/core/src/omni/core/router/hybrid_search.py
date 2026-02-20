"""
hybrid_search.py - Hybrid Search Engine (Rust-Native Implementation)

This module provides a thin Python shell over Rust's omni-vector search.
All heavy lifting (vector search, keyword rescue, scoring, fusion) is done in Rust.

Rust Benefits:
- Zero serialization overhead (no Python->Rust->Python data copying)
- High-performance L2 distance computation
- Integrated Tantivy BM25 keyword search
- Atomic hybrid scoring (Keyword Rescue pattern)

Architecture:
    User Query
        │
        ▼
    Embedding (Python)
        │
        ▼
    ┌─────────────────────────────────────────┐
    │         Rust omni-vector Search         │
    │  ┌─────────────────┬─────────────────┐  │
    │  │  LanceDB        │   Tantivy       │  │
    │  │  (Vector)       │   (Keyword)     │  │
    │  │  weight=dynamic │   weight=dynamic│  │
    │  └─────────────────┴─────────────────┘  │
    │                    │                    │
    │         Weighted RRF Fusion +          │
    │         Field Boosting                 │
    │  (NAME_TOKEN_BOOST=0.5,               │
    │   EXACT_PHRASE_BOOST=1.5)              │
    └─────────────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────────────┐
    │           Python Post-Processing        │
    │  - Contract validation                 │
    │  - Result formatting                   │
    └─────────────────────────────────────────┘
                    │
                    ▼
    List[dict] with: id, score, confidence, skill_name, command, etc.

Usage:
    search = HybridSearch()
    results = await search.search("git commit", limit=5)

    # With threshold filtering
    results = await search.search("find files", limit=10, min_score=0.4)

    # Check confidence
    for r in results:
        if r["confidence"] == "high":
            print(f"Best match: {r['id']} (score={r['score']:.2f})")
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Awaitable

from omni.foundation.config.logging import get_logger

# Minimum attribute overlap strength (query terms in routing_keywords/intents/category) to promote medium -> high
_ATTR_MIN_OVERLAP_STRENGTH = 2
# Intent-overlap boost: per-hit weight when query intent terms match tool routing_keywords/intents (data-driven)
_INTENT_OVERLAP_BOOST_PER_HIT = 0.15
# Minimum gap between #1 and #2 score for clear-winner high confidence
_CLEAR_WINNER_GAP = 0.15

from omni.foundation.services.vector_schema import (
    build_tool_router_result,
    parse_tool_search_payload,
)

if TYPE_CHECKING:
    from omni.foundation.bridge.rust_vector import RustVectorStore

logger = get_logger("omni.core.router.hybrid")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)
_TOOL_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,160}$")

# ---------------------------------------------------------------------------
# Parameter-type tokens that the normalizer inserts as URL/path placeholders.
# These are entity indicators (what the user provides), NOT intent indicators
# (what the user wants to do). Stripped from BM25 keyword text so TF-IDF
# ranking is driven by intent verbs, not parameter types.
# ---------------------------------------------------------------------------
_PARAM_TOKEN_RE = re.compile(
    r"\b(github\s+url|url|link|https?|http)\b",
    re.IGNORECASE,
)

# Lightweight stop words that carry no intent signal. Removing them sharpens
# both BM25 and embedding focus on intent verbs. This list is intentionally
# small (standard English function words); no skill-specific terms.
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "am",
        "do",
        "does",
        "did",
        "will",
        "would",
        "shall",
        "should",
        "can",
        "could",
        "may",
        "might",
        "must",
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "it",
        "they",
        "them",
        "his",
        "her",
        "its",
        "their",
        "to",
        "of",
        "in",
        "on",
        "at",
        "for",
        "with",
        "from",
        "by",
        "about",
        "into",
        "through",
        "during",
        "before",
        "after",
        "and",
        "or",
        "but",
        "not",
        "no",
        "nor",
        "that",
        "this",
        "these",
        "those",
        "help",
        "please",
        "want",
        "need",
        "like",
    }
)


def _extract_keyword_text(query: str) -> str:
    """Produce intent-focused text for search (both BM25 and embedding).

    Two-stage cleanup:
    1. **Parameter stripping**: Remove URL/link tokens inserted by the normalizer
       (``github url``, ``url``, ``link``). These are parameter-type indicators that
       bias BM25 toward parameter-handling skills (e.g. crawl4ai) instead of
       intent-matching skills (e.g. researcher).
    2. **Stop-word removal**: Remove common function words ("help", "me", "to", etc.)
       that dilute intent signal in both BM25 and embedding. Only a small, universal
       set is removed — no skill-specific logic.

    This function is data-driven and skill-agnostic. It scales to any number of
    skills without modification.

    Examples:
        "help me to research github url" → "research"
        "help me analyze github url" → "analyze"
        "crawl url" → "crawl"
        "git commit with message" → "git commit message"

    Args:
        query: Normalized query (after URL replacement by normalize_for_routing).

    Returns:
        Intent-focused text for search.
    """
    # Stage 1: strip parameter-type tokens
    text = _PARAM_TOKEN_RE.sub("", query)
    # Stage 1b: normalize punctuation separators (/, -, etc.) to spaces.
    # Without this, "analyze/research" is a single Tantivy token → 0 BM25 hits.
    # With spaces, Tantivy correctly tokenizes → "analyze" + "research" → strong hits.
    text = re.sub(r"[/\-_]+", " ", text)
    # Stage 2: strip stop words (token-level, preserves order)
    tokens = text.split()
    intent_tokens = [t for t in tokens if t.lower().strip(".,!?") not in _STOP_WORDS]
    text = " ".join(intent_tokens)
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else query  # fallback to full query if everything was stripped


def _detect_param_types(query: str) -> list[str]:
    """Detect parameter types present in the (normalized) query.

    Returns a list of detected types (e.g. ["url"]) which can be used
    for schema-aware boosting: tools whose input_schema has a matching
    parameter get a small bonus.

    Data-driven: works for any skill; no skill-specific logic.
    """
    types: list[str] = []
    q_lower = query.lower()
    if "url" in q_lower or "link" in q_lower or "http" in q_lower:
        types.append("url")
    if re.search(r"(/\w[\w/.-]+|\w:\\)", query):
        types.append("path")
    return types


# Boost applied per matching parameter type in a tool's input_schema
_PARAM_SCHEMA_BOOST = 0.10
# Research+URL boost: when query has research/analyze intent and URL, favor repo-analyzing tools (researcher) over page-fetch tools (crawl4ai)
_RESEARCH_URL_BOOST = 0.35
# When query has concrete URL (https://...), fetch more Rust candidates so URL tools (crawl4ai) can enter top-N.
_CONCRETE_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _query_has_concrete_url(query: str) -> bool:
    """True if query contains a concrete URL. Use original query; effective_query replaces URL with 'github url'."""
    return bool(query and _CONCRETE_URL_RE.search(query))


def _match_param_type_to_schema(param_type: str, schema: Any) -> bool:
    """Check if a tool's input_schema has a parameter matching the detected type."""
    if not schema or not isinstance(schema, dict):
        return False
    props = schema.get("properties", {})
    if not isinstance(props, dict):
        return False
    for name in props:
        name_lower = name.lower()
        if param_type == "url" and any(x in name_lower for x in ("url", "uri", "link")):
            return True
        if param_type == "path" and any(x in name_lower for x in ("path", "file", "directory")):
            return True
    return False


def _apply_param_schema_boost(
    results: list[dict[str, Any]], param_types: list[str]
) -> list[dict[str, Any]]:
    """Boost tools whose input_schema accepts detected parameter types.

    This is purely data-driven: uses indexed input_schema (no hardcoded skill names).
    Scales to any number of skills and parameter types.
    """
    if not results or not param_types:
        return results
    import json as _json

    for r in results:
        raw_schema = r.get("input_schema") or {}
        if isinstance(raw_schema, str):
            try:
                raw_schema = _json.loads(raw_schema) if raw_schema.strip() else {}
            except Exception:
                raw_schema = {}
        for ptype in param_types:
            if _match_param_type_to_schema(ptype, raw_schema):
                s = float(r.get("score") or 0)
                f = float(r.get("final_score") or s)
                r["score"] = s + _PARAM_SCHEMA_BOOST
                r["final_score"] = f + _PARAM_SCHEMA_BOOST
                break  # one boost per result
    results.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    return results


def _is_researcher_like_tool(r: dict[str, Any]) -> bool:
    """True if tool has research/analyze AND repo/repository in routing_keywords (data-driven, no skill names)."""
    kw = r.get("routing_keywords") or []
    kw_joined = " ".join(str(k).lower() for k in kw)
    has_research = "research" in kw_joined or "analyze" in kw_joined
    has_repo = any(x in kw_joined for x in ("repo", "repository", "analyze_repo", "git"))
    return has_research and has_repo


def _apply_research_url_boost(
    results: list[dict[str, Any]], effective_query: str, param_types: list[str]
) -> list[dict[str, Any]]:
    """Boost researcher-like tools when query has research/analyze intent + URL.

    For 'help me research https://github.com/...', researcher (analyze repo) should
    rank above crawl4ai (fetch page). Data-driven: uses routing_keywords, no skill names.
    """
    if not results or "url" not in param_types:
        return results
    intent_terms = _intent_terms_from_query(effective_query)
    if not intent_terms or not (intent_terms & {"research", "analyze", "analyzing"}):
        return results
    for r in results:
        if _is_researcher_like_tool(r):
            s = float(r.get("score") or 0)
            f = float(r.get("final_score") or s)
            r["score"] = s + _RESEARCH_URL_BOOST
            r["final_score"] = f + _RESEARCH_URL_BOOST
    results.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    return results


def _query_terms_for_attribute_match(query: str) -> set[str]:
    """Normalize query for attribute overlap: strip URLs, tokenize, keep words >= 2 chars."""
    cleaned = re.sub(r"https?://\S+", " ", query)
    tokens = re.findall(r"[A-Za-z0-9]+", cleaned.lower())
    return {t for t in tokens if len(t) >= 2}


def _attribute_overlap_strength(
    query_terms: set[str],
    routing_keywords: list[str],
    intents: list[str],
    category: str,
) -> int:
    """Count how many query terms appear in routing_keywords, intents, or category. Used for confidence."""
    keywords_lower = [k.lower() for k in routing_keywords]
    intents_lower = [i.lower() for i in intents]
    cat_lower = category.lower() if category else ""
    hits = 0
    for term in query_terms:
        if any(term in kw for kw in keywords_lower) or term in " ".join(keywords_lower):
            hits += 2
        elif any(term in it for it in intents_lower) or term in " ".join(intents_lower):
            hits += 1
        elif cat_lower and term in cat_lower:
            hits += 1
    return hits


def _apply_attribute_confidence(
    results: list[dict[str, Any]], effective_query: str
) -> list[dict[str, Any]]:
    """Promote medium -> high when query terms strongly overlap tool routing_keywords/intents/category."""
    if not results or not effective_query:
        return results
    terms = _query_terms_for_attribute_match(effective_query)
    if not terms:
        return results
    for r in results:
        if r.get("confidence") != "medium":
            continue
        kw = r.get("routing_keywords") or []
        meta = r.get("payload") or {}
        meta = meta.get("metadata") or meta
        intents_list = meta.get("intents") or r.get("intents") or []
        cat = meta.get("category") or r.get("category") or ""
        strength = _attribute_overlap_strength(terms, kw, intents_list, cat)
        if strength >= _ATTR_MIN_OVERLAP_STRENGTH:
            r["confidence"] = "high"
            logger.debug(
                "Attribute confidence: promoted to high",
                id=r.get("id"),
                overlap_strength=strength,
            )
    return results


def _intent_terms_from_query(query: str) -> set[str]:
    """Extract salient intent terms from query for attribute-based boost (data-driven; vocab from config)."""
    if not query or not query.strip():
        return set()
    from omni.foundation.config.settings import get_setting

    q = query.strip().lower()
    tokens = set(re.findall(r"[a-z0-9]+", q))
    custom = get_setting("router.search.intent_vocab")
    if isinstance(custom, (list, tuple)) and len(custom) > 0:
        intent_vocab = {str(t).strip().lower() for t in custom}
    else:
        intent_vocab = {
            "research",
            "analyze",
            "analyzing",
            "crawl",
            "commit",
            "search",
            "find",
            "recall",
            "save",
        }
    return tokens & intent_vocab


def _apply_intent_overlap_boost(
    results: list[dict[str, Any]], effective_query: str
) -> list[dict[str, Any]]:
    """Boost results whose routing_keywords/intents overlap query intent terms (data-driven, scales to any skills)."""
    if not results or not effective_query:
        return results
    intent_terms = _intent_terms_from_query(effective_query)
    if not intent_terms:
        return results
    for r in results:
        kw = r.get("routing_keywords") or []
        meta = r.get("payload") or {}
        meta = meta.get("metadata") if isinstance(meta, dict) else {}
        if not isinstance(meta, dict):
            meta = {}
        intents_list = meta.get("intents") or r.get("intents") or []
        cat = meta.get("category") or r.get("category") or ""
        strength = _attribute_overlap_strength(intent_terms, kw, intents_list, cat)
        if strength > 0:
            boost = min(0.5, strength * _INTENT_OVERLAP_BOOST_PER_HIT)
            s = float(r.get("score") or 0)
            f = float(r.get("final_score") or s)
            r["score"] = s + boost
            r["final_score"] = f + boost
    results.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    return results


def _recalibrate_confidence(
    results: list[dict[str, Any]],
    profile: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Re-calibrate confidence labels after Python-side score boosts.

    Uses a **hybrid absolute + relative** approach:
    - Absolute thresholds from the profile prevent labeling noise as "high".
    - Relative thresholds from the top score prevent inflated tiers when all
      scores are high (e.g. strong keyword matches inflate everything).

    Algorithm:
    1. Compute absolute tier from profile thresholds (same as Rust-side).
    2. Compute relative tier from top_score ratios:
       - high: score >= top * HIGH_RATIO (within 65% of best)
       - medium: score >= top * MEDIUM_RATIO (within 40% of best)
       - low: everything else
    3. Final tier = min(absolute_tier, relative_tier).
       This means a result must pass BOTH absolute and relative checks.
    4. Clear-winner promotion: if #1 is far ahead of #2, promote to high.
    """
    if not results:
        return results

    # Load profile thresholds (same source as Rust-side calibration)
    if profile is None:
        from omni.foundation.config.settings import get_setting

        p = get_setting("router.search.profiles.balanced")
        profile = p if isinstance(p, dict) else {}

    high_threshold = float(profile.get("high_threshold", 0.75))
    medium_threshold = float(profile.get("medium_threshold", 0.50))
    high_base = float(profile.get("high_base", 0.90))
    high_scale = float(profile.get("high_scale", 0.05))
    high_cap = float(profile.get("high_cap", 0.99))
    medium_base = float(profile.get("medium_base", 0.60))
    medium_scale = float(profile.get("medium_scale", 0.30))
    medium_cap = float(profile.get("medium_cap", 0.89))
    low_floor = float(profile.get("low_floor", 0.10))

    # Relative thresholds based on top score
    _HIGH_RATIO = 0.65  # within 35% of top → eligible for high
    _MEDIUM_RATIO = 0.40  # within 60% of top → eligible for medium

    top_score = float(results[0].get("score") or 0) if results else 0.0
    rel_high = top_score * _HIGH_RATIO
    rel_medium = top_score * _MEDIUM_RATIO

    _TIER_RANK = {"high": 2, "medium": 1, "low": 0}

    for idx, r in enumerate(results):
        score = float(r.get("score") or 0)

        # Absolute tier from profile thresholds
        if score >= high_threshold:
            abs_tier = "high"
        elif score >= medium_threshold:
            abs_tier = "medium"
        else:
            abs_tier = "low"

        # Relative tier from top-score ratios
        if score >= rel_high:
            rel_tier = "high"
        elif score >= rel_medium:
            rel_tier = "medium"
        else:
            rel_tier = "low"

        # Final tier = min(absolute, relative) → must pass both
        conf = abs_tier if _TIER_RANK[abs_tier] <= _TIER_RANK[rel_tier] else rel_tier

        # Clear winner: #1 far ahead of #2 → promote to high
        if idx == 0 and conf != "high" and len(results) > 1:
            second_score = float(results[1].get("score") or 0)
            if score >= medium_threshold and (score - second_score) >= _CLEAR_WINNER_GAP:
                conf = "high"

        # Compute final_score per tier
        if conf == "high":
            final = min(high_base + score * high_scale, high_cap)
        elif conf == "medium":
            final = min(medium_base + score * medium_scale, medium_cap)
        else:
            final = max(score, low_floor)

        r["confidence"] = conf
        r["final_score"] = final

    return results


def _is_routable_tool_name(value: str) -> bool:
    name = value.strip()
    if not name:
        return False
    if _UUID_RE.match(name):
        return False
    if not _TOOL_ID_RE.match(name):
        return False
    for segment in name.split("."):
        if _UUID_RE.match(segment):
            return False
    return any(ch.isalpha() for ch in name)


class HybridMatch:
    """Represents a match from hybrid search (Rust-native).

    This class is used internally by Rust-to-Python result conversion.
    In practice, results are returned as dicts from `search()` method.

    Attributes:
        id: Tool identifier in "skill.command" format (e.g., "git.commit").
        content: Tool description from indexed content.
        semantic_score: Raw vector similarity score from LanceDB (0.0-1.0).
        keyword_score: BM25 score from Tantivy keyword search.
        combined_score: Final Weighted RRF score after fusion and boosting.
        confidence: Human-readable confidence level ("high", "medium", "low").
        final_score: Display-calibrated score for UI/thresholding.
        metadata: Additional tool metadata (skill_name, file_path, etc.).
    """

    model_config = {"frozen": True}

    id: str
    content: str
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    combined_score: float = 0.0
    confidence: str = "unknown"
    final_score: float = 0.0
    metadata: dict[str, Any] = {}


class HybridSearch:
    """Rust-Native Hybrid Search Engine.

    Thin Python shell over Rust omni-vector. All search logic is in Rust:
    - Vector similarity search (LanceDB with normalized vectors)
    - Keyword rescue (Tantivy BM25 for exact/partial matches)
    - Weighted RRF fusion with field boosting

    Rust performs all heavy computation; Python handles:
    - Embedding generation for vector search
    - Canonical payload validation for downstream consumers

    Intent extraction is handled by the discovery node LLM prompt.

    Example:
        ```python
        search = HybridSearch()

        # Basic search
        results = await search.search("find files", limit=5)

        # With threshold filtering
        results = await search.search(
            query="git commit",
            limit=10,
            min_score=0.4  # Only return medium+ confidence results
        )

        # Process results
        for r in results:
            if r["confidence"] == "high":
                print(f"Best: {r['id']} (score={r['score']:.2f})")
        ```

    Attributes:
        _store: Rust vector store instance (LanceDB + Tantivy).
        _embed_service: Lazy-loaded embedding service.

    See Also:
        - omni.core.router.main.OmniRouter: Higher-level router facade
        - omni.core.skills.discovery.SkillDiscoveryService: Tool discovery service
    """

    def __init__(self, storage_path: str | None = None) -> None:
        """Initialize hybrid search with Rust vector store.

        The vector store is cached globally to avoid repeated initialization.
        Embedding service is loaded lazily on first use.

        Uses the skills DB path by default so that the same store (and Tantivy
        keyword index at skills.lance/keyword_index) is used as reindex. Otherwise
        route test would use base_path/keyword_index which sync never updates.
        """
        from omni.foundation.bridge.rust_vector import get_vector_store
        from omni.foundation.config.database import get_database_path
        from omni.foundation.config.dirs import get_vector_db_path

        resolved_storage_path = storage_path
        if storage_path is None:
            # BUG FIX: get_database_path("skills") returns skills.lance subdirectory,
            # but LanceDB has a bug where agentic_search returns empty in subdirectories.
            # Use root vector db path instead (same as SkillDiscoveryService).
            resolved_storage_path = str(get_vector_db_path())
        elif storage_path != ":memory:" and storage_path.endswith(".lance"):
            resolved_storage_path = str(Path(storage_path).parent)
        self._store = get_vector_store(resolved_storage_path)
        self._storage_path = resolved_storage_path
        # Custom embedding function (set by CLI for MCP server access)
        self._embed_func: Callable[[list[str]], Awaitable[list[list[float]]]] | None = None
        self._relationship_graph: dict[str, list[tuple[str, float]]] | None = None

    def _get_relationship_graph(self) -> dict[str, list[tuple[str, float]]] | None:
        """Lazy-load skill relationship graph for associative rerank."""
        if self._relationship_graph is not None:
            return self._relationship_graph
        try:
            from omni.foundation.config.dirs import get_vector_db_path

            from omni.core.router.skill_relationships import (
                get_relationship_graph_path,
                load_relationship_graph,
            )

            base = self._storage_path or get_vector_db_path()
            path = get_relationship_graph_path(str(base) if base else None)
            if path:
                self._relationship_graph = load_relationship_graph(path)
        except Exception:
            self._relationship_graph = {}
        return self._relationship_graph

    async def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
        confidence_profile: dict[str, float] | None = None,
        intent_override: str | None = None,
        skip_translation: bool = False,
        record_timings: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        """Perform hybrid search using Rust omni-vector engine.

        This method orchestrates the full hybrid search pipeline:
        1. Generate query embedding (semantic search)
        2. Normalize query for keyword search pipeline
        3. Call Rust search_tools for vector + keyword fusion
        4. Apply metadata-aware rerank (always on in hybrid)
        5. Calibrate confidence levels for downstream consumers

        Args:
            query: Natural language search query (e.g., "find files matching 'pub updated'").
                The query is used both for semantic embedding and keyword matching.
            limit: Maximum number of results to return. Default is 5.
            min_score: Minimum combined score threshold (0.0-1.0). Results below this
                threshold are filtered out. Use 0.4 for "medium+" confidence only.
            intent_override: Optional intent hint (e.g. from an LLM). When set, used
                instead of rule-based classification. One of "exact", "semantic", "hybrid", "category".
            skip_translation: If True, do not translate non-English query; use as-is with embedding.
                Speeds up routing when embedding is multilingual (e.g. route test).

        Returns:
            List of result dictionaries, sorted by score descending. Each dict contains:
            - id: Tool identifier (e.g., "git.commit")
            - content: Tool description
            - score: Raw RRF score from Rust (0.0-2.0+)
            - confidence: "high", "medium", or "low"
            - final_score: Display-calibrated score (0.0-1.0)
            - skill_name: Skill name (e.g., "git")
            - command: Command name (e.g., "commit")
            - file_path: Source file path
            - routing_keywords: Indexed routing keywords
            - input_schema: JSON schema for tool parameters
            - payload: Complete metadata for routing

        Example:
            ```python
            results = await search.search("git commit message", limit=3)
            for r in results:
                print(f"{r['id']}: {r['confidence']} (score={r['score']:.2f})")
            # Output:
            # git.commit: high (score=1.00)
            # git.smart_commit: high (score=0.95)
            ```

        Note:
            Query cleaning removes characters that cause Tantivy parse errors:
            quotes, brackets, parentheses, braces. The original query is used
            for embedding generation to preserve semantic meaning.

        See Also:
            - Rust omni-vector hybrid search for underlying algorithm
        """
        _t_search_start = time.perf_counter() if record_timings is not None else None
        # Optional: translate non-English query to English (SKILL.md is English-only)
        from omni.core.router.translate import translate_query_to_english

        from omni.core.router.query_normalizer import normalize_for_routing

        effective_query = await translate_query_to_english(query, enabled=not skip_translation)
        if effective_query != query:
            logger.info(
                "Effective query (after translation) for routing",
                original_preview=query[:50],
                effective_preview=effective_query[:80],
            )
        effective_query = normalize_for_routing(effective_query)

        # --- Intent-focused text for both BM25 and embedding ---
        # Parameter tokens (e.g. "url", "github url") inserted by the normalizer
        # are entity indicators, not intent. Stripping them from BOTH keyword
        # search and embedding focuses ranking on what the user wants to DO
        # (research, analyze, crawl) rather than what they're providing as input.
        # This is data-driven: detects parameter patterns generically, no skill-specific rules.
        intent_text = _extract_keyword_text(effective_query)
        param_types = _detect_param_types(effective_query)
        if intent_text != effective_query:
            logger.debug(
                "Dual-signal decomposition: intent_text=%r, param_types=%r (from %r)",
                intent_text,
                param_types,
                effective_query,
            )

        # Get query embedding from intent-focused text (required for vector search)
        if record_timings is not None and _t_search_start is not None:
            record_timings["pre_embed_s"] = time.perf_counter() - _t_search_start
        _t_embed_0 = time.perf_counter() if record_timings is not None else None
        if self._embed_func is not None:
            # Custom embedding function (async)
            vectors = await self._embed_func([intent_text])
            if vectors and len(vectors) > 0:
                query_vector = vectors[0]
            else:
                # Fallback to local embedding
                embed_service = self._get_embed_service()
                query_vector = embed_service.embed(intent_text)[0]
        else:
            # Default: use local embedding service
            embed_service = self._get_embed_service()
            query_vector = embed_service.embed(intent_text)[0]
        if record_timings is not None and _t_embed_0 is not None:
            record_timings["embed_s"] = time.perf_counter() - _t_embed_0
        _t_embed_end = time.perf_counter() if record_timings is not None else None

        # Use agentic search when available (intent + category_filter from rule-based or optional LLM).
        from omni.foundation.config.settings import get_setting

        from omni.core.router.query_intent import (
            classify_tool_search_intent_full,
            classify_tool_search_intent_with_llm,
        )

        if intent_override is not None:
            resolved_intent, category_filter = intent_override, None
        elif get_setting("router.intent.use_llm"):
            intent_result = await classify_tool_search_intent_with_llm(effective_query)
            if intent_result is not None:
                resolved_intent, category_filter = (
                    intent_result.intent,
                    intent_result.category_filter,
                )
            else:
                intent_result = classify_tool_search_intent_full(effective_query)
                resolved_intent, category_filter = (
                    intent_result.intent,
                    intent_result.category_filter,
                )
        else:
            intent_result = classify_tool_search_intent_full(effective_query)
            resolved_intent, category_filter = intent_result.intent, intent_result.category_filter
        # --- Dual-Core Fusion Weights ---
        # Compute once, apply to both Rust search engine and Python-side bridges.
        # This ensures a single intent analysis drives the entire pipeline.
        fusion = None
        try:
            from omni.rag.dual_core import compute_fusion_weights

            fusion = compute_fusion_weights(effective_query)
        except Exception:
            pass  # Non-fatal; defaults will be used

        # Rerank is always on in hybrid search (metadata-aware boost after RRF fusion).
        fusion_kw = {}
        if fusion is not None:
            fusion_kw = {
                "semantic_weight": fusion.vector_weight,
                "keyword_weight": fusion.keyword_weight,
            }

        # When query has concrete URL, fetch more candidates so URL-accepting tools (crawl4ai) can enter top-N.
        # effective_query replaces "https://..." with "github url", so use original query for this check.
        has_concrete_url = "url" in param_types and _query_has_concrete_url(query)
        has_rerank_signals = bool(param_types) or bool(_intent_terms_from_query(effective_query))
        rust_limit = min(limit * 20, 200) if (has_rerank_signals and has_concrete_url) else limit

        if record_timings is not None and _t_embed_end is not None:
            record_timings["intent_fusion_s"] = time.perf_counter() - _t_embed_end
        _t_rust_0 = time.perf_counter() if record_timings is not None else None
        keyword_text = intent_text
        if has_concrete_url:
            intent_terms_for_kw = _intent_terms_from_query(effective_query)
            if intent_terms_for_kw and intent_terms_for_kw & {"research", "analyze", "analyzing"}:
                # Research+URL: favor researcher (analyze repo) but keep crawl4ai in candidates
                keyword_text = (
                    f"{intent_text} analyze repo research repository crawl url fetch".strip()
                )
            else:
                keyword_text = f"{intent_text} crawl url fetch web page".strip()
        if hasattr(self._store, "agentic_search"):
            results = await self._store.agentic_search(
                table_name="skills",
                query_vector=query_vector,
                query_text=keyword_text,
                limit=rust_limit,
                threshold=min_score,
                intent=resolved_intent,
                confidence_profile=confidence_profile,
                rerank=True,
                category_filter=category_filter,
                **fusion_kw,
            )
            # Fallback: if category filter returned no results, retry without filter so we still return matches.
            if not results and category_filter:
                logger.debug(
                    "Hybrid search: 0 results with category_filter=%s, retrying without filter",
                    category_filter,
                )
                results = await self._store.agentic_search(
                    table_name="skills",
                    query_vector=query_vector,
                    query_text=keyword_text,
                    limit=rust_limit,
                    threshold=min_score,
                    intent=resolved_intent,
                    confidence_profile=confidence_profile,
                    rerank=True,
                    category_filter=None,
                    **fusion_kw,
                )
        else:
            results = await self._store.search_tools(
                table_name="skills",
                query_vector=query_vector,
                query_text=keyword_text,
                limit=rust_limit,
                threshold=min_score,
                confidence_profile=confidence_profile,
                rerank=True,
            )
        if record_timings is not None and _t_rust_0 is not None:
            record_timings["rust_s"] = time.perf_counter() - _t_rust_0
        _t_rust_end = time.perf_counter() if record_timings is not None else None

        # Format results for Python consumers
        formatted = []
        if not results:
            try:
                info = await self._store.get_table_info("skills")
                n = (info or {}).get("row_count") or 0
                if n and int(n) > 0:
                    logger.info(
                        "Router returned 0 results but skills table has %s tools. "
                        "Check that embedding.dimension in settings matches the index (e.g. run 'omni sync' and use same embedding source).",
                        n,
                    )
            except Exception:
                pass
        for raw in results:
            candidate = dict(raw)
            try:
                payload = parse_tool_search_payload(candidate)
            except Exception as exc:
                logger.debug(f"Skipping invalid tool search payload: {exc}")
                continue

            raw_score = payload.score
            confidence = payload.confidence
            final_score = payload.final_score

            # Canonicalize tool_name to "skill.command".
            # Prefer routed canonical name from payload.name when available.
            raw_tool_name = payload.tool_name.strip()
            canonical_name = payload.name.strip()
            if _is_routable_tool_name(canonical_name) and "." in canonical_name:
                full_tool_name = canonical_name
            elif "." not in raw_tool_name and payload.skill_name:
                full_tool_name = f"{payload.skill_name}.{raw_tool_name}"
            else:
                full_tool_name = raw_tool_name
            if not _is_routable_tool_name(full_tool_name):
                logger.debug("Skipping non-routable tool_name: %s", full_tool_name)
                continue
            command = (
                ".".join(full_tool_name.split(".")[1:]) if "." in full_tool_name else full_tool_name
            )
            if not command:
                continue

            router_result = build_tool_router_result(payload, full_tool_name)
            router_result["score"] = raw_score
            router_result["final_score"] = final_score
            router_result["confidence"] = confidence
            if payload.vector_score is not None:
                router_result["vector_score"] = float(payload.vector_score)
            if payload.keyword_score is not None:
                router_result["keyword_score"] = float(payload.keyword_score)
            formatted.append(router_result)

        formatted = _apply_attribute_confidence(formatted, effective_query)
        formatted = _apply_intent_overlap_boost(formatted, effective_query)
        # Schema-aware boost: tools whose input_schema accepts detected param types get a bonus
        if param_types:
            formatted = _apply_param_schema_boost(formatted, param_types)
        # Research+URL: when user says "research [URL]", favor researcher over crawl4ai
        formatted = _apply_research_url_boost(formatted, effective_query, param_types)
        # Associative rerank: boost tools related to top results (relationship graph)
        graph = self._get_relationship_graph()
        if graph:
            from omni.core.router.skill_relationships import apply_relationship_rerank

            formatted = apply_relationship_rerank(formatted, graph)

        # KG query-time rerank: boost tools connected to query entities
        # via KnowledgeGraph multi-hop traversal (Bridge 5: KG → Router)
        # Reuses the fusion weights computed above (single intent analysis).
        if fusion is not None:
            try:
                from omni.rag.dual_core import apply_kg_rerank

                formatted = apply_kg_rerank(
                    formatted, effective_query, fusion_scale=fusion.kg_rerank_scale
                )
            except Exception:
                pass  # Non-fatal; KG rerank is optional

        # Re-calibrate confidence after all Python-side boosts.
        # Rust assigned confidence on pre-boost raw RRF scores; Python boosts
        # (intent overlap, param schema, relationship rerank) can significantly
        # increase scores. Without re-calibration, a tool boosted from 0.3 to 1.0
        # would still show "low" confidence.
        formatted = _recalibrate_confidence(formatted, confidence_profile)

        if len(formatted) > limit:
            formatted = formatted[:limit]

        if record_timings is not None and _t_rust_end is not None:
            record_timings["post_rust_s"] = time.perf_counter() - _t_rust_end
        logger.debug(f"Hybrid search for '{query}': {len(formatted)} results")
        return formatted

    def _get_embed_service(self) -> Any:
        """Lazily load and return the embedding service.

        The embedding service is loaded on first use to avoid initialization
        overhead during module import. Thread-safe via double-checked locking.

        Returns:
            EmbeddingService: Service for generating query embeddings.

        Raises:
            RuntimeError: If embedding service cannot be initialized.
        """
        if not hasattr(self, "_embed_service"):
            from omni.foundation.services.embedding import get_embedding_service

            self._embed_service = get_embedding_service()
        return self._embed_service

    def set_weights(self, semantic: float, keyword: float) -> None:
        """Set search weights for RRF fusion.

        These weights are passed to the Rust search engine at query time
        via the ``agentic_search`` API. When not set, Rust defaults apply
        (SEMANTIC_WEIGHT=1.0, KEYWORD_WEIGHT=1.5).

        Note: This is now a live override. The ``compute_fusion_weights``
        system may also set these dynamically per-query based on intent.

        Args:
            semantic: Weight for vector (semantic) search contribution.
            keyword: Weight for BM25 keyword search contribution.
        """
        self._manual_semantic_weight = semantic
        self._manual_keyword_weight = keyword
        logger.info("Weights set: semantic=%.2f, keyword=%.2f", semantic, keyword)

    def get_weights(self) -> tuple[float, float]:
        """Get the current search weights used by Rust.

        These are the fixed weights defined in Rust's omni-vector crate.

        Returns:
            Tuple of (semantic_weight, keyword_weight) = (1.0, 1.5).

        Note:
            The keyword weight is higher because exact keyword matches
            are more reliable indicators of relevance for tool search.
        """
        profile = self._store.get_search_profile()
        return (
            float(profile.get("semantic_weight", 1.0)),
            float(profile.get("keyword_weight", 1.5)),
        )

    def stats(self) -> dict[str, Any]:
        """Get hybrid search engine statistics and configuration.

        Returns a dictionary containing the current search configuration
        and algorithm parameters. Useful for debugging and monitoring.

        Returns:
            Dict with keys:
            - semantic_weight: Weight for vector search (1.0)
            - keyword_weight: Weight for keyword search (1.5)
            - rrf_k: RRF smoothing parameter (10)
            - implementation: Implementation name
            - strategy: Fusion strategy used
            - field_boosting: Token/phrase boost values
        """
        return self._store.get_search_profile()


__all__ = ["HybridSearch", "HybridMatch"]
