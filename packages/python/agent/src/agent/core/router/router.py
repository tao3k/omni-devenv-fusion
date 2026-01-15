"""
agent/core/router/router.py
Phase 67: Adaptive Context - Intent-Driven Tool Loading

Router for intent-driven tool loading using hybrid search.

Features:
- Simple keyword extraction (no heavy NLP)
- Hybrid search (vector + keywords)
- Tool recommendation based on user intent
"""

import re
from typing import Any

_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


class IntentRouter:
    """
    Router for intent-driven tool loading using hybrid search.

    This class provides a simple interface for:
    - Extracting keywords from user queries
    - Searching tools using hybrid (vector + keyword) search
    - Ranking tools by relevance to intent
    """

    _instance: "IntentRouter | None" = None

    def __new__(cls) -> "IntentRouter":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

    def extract_keywords(self, text: str) -> list[str]:
        """
        Extract keywords from text using simple regex/split.

        This is a lightweight alternative to full NLP.
        - Lowercases text
        - Extracts alphanumeric tokens (2+ chars)
        - Filters common stopwords

        Args:
            text: Input text (e.g., user query)

        Returns:
            List of extracted keywords
        """
        if not text:
            return []

        # Lowercase
        text = text.lower()

        # Extract alphanumeric tokens (2+ chars)
        tokens = re.findall(r"\b[a-z0-9]{2,}\b", text)

        # Common English stopwords to filter
        stopwords = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "need",
            "dare",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "and",
            "but",
            "or",
            "nor",
            "so",
            "yet",
            "both",
            "either",
            "neither",
            "not",
            "only",
            "just",
            "also",
            "very",
            "too",
            "quite",
            "rather",
            "this",
            "that",
            "these",
            "those",
            "what",
            "which",
            "who",
            "whom",
            "where",
            "when",
            "why",
            "how",
            "all",
            "each",
            "every",
            "any",
            "some",
            "no",
            "my",
            "your",
            "his",
            "her",
            "its",
            "our",
            "their",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "me",
            "him",
            "us",
            "them",
            "myself",
            "yourself",
            "himself",
            "herself",
            "itself",
            "help",
            "please",
            "thanks",
            "thank",
            "want",
            "like",
            "know",
            "think",
            "make",
            "get",
            "let",
            "use",
            "find",
            "give",
            "tell",
        }

        # Filter stopwords and return unique keywords
        keywords = list(dict.fromkeys(t for t in tokens if t not in stopwords))
        return keywords

    async def search_tools(
        self,
        query: str,
        keywords: list[str] | None = None,
        limit: int = 15,
    ) -> list[dict[str, Any]]:
        """
        Search tools using hybrid search (vector + keywords).

        Args:
            query: Natural language query describing what the user needs.
            keywords: Optional explicit keywords to boost.
            limit: Maximum number of results (default: 15).

        Returns:
            List of tool dictionaries with keys:
            - id: Tool name (e.g., "git.commit")
            - content: Tool description
            - metadata: Tool metadata (skill_name, schema, etc.)
            - distance: Hybrid score (lower = better)
        """
        # Use provided keywords or extract from query
        search_keywords = keywords or self.extract_keywords(query)

        # Import VectorMemory
        from agent.core.vector_store import get_vector_memory

        vm = get_vector_memory()

        try:
            results = await vm.search_tools_hybrid(
                query=query,
                keywords=search_keywords,
                limit=limit,
            )
            return results
        except Exception as e:
            _get_logger().error("IntentRouter.search_tools failed", error=str(e))
            return []

    def rank_tools(
        self,
        query: str,
        tools: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Rank tools by relevance to query.

        Args:
            query: User query
            tools: List of tool dictionaries
            top_k: Number of top tools to return

        Returns:
            Ranked list of tools
        """
        # Extract keywords from query
        query_keywords = set(self.extract_keywords(query))

        # Score each tool
        scored = []
        for tool in tools:
            score = 0.0
            metadata = tool.get("metadata", {}) or {}

            # Check tool name
            tool_name = tool.get("id", "").lower()
            for kw in query_keywords:
                if kw in tool_name:
                    score += 0.3

            # Check skill name
            skill_name = metadata.get("skill_name", "").lower()
            for kw in query_keywords:
                if kw in skill_name:
                    score += 0.2

            # Check description
            content = tool.get("content", "").lower()
            for kw in query_keywords:
                if kw in content:
                    score += 0.1

            # Check keywords array
            tool_keywords = metadata.get("keywords", [])
            for kw in query_keywords:
                if kw in tool_keywords:
                    score += 0.2

            scored.append((score, tool))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        return [t for _, t in scored[:top_k]]


# Singleton accessor
_router: IntentRouter | None = None


def get_intent_router() -> IntentRouter:
    """Get the IntentRouter singleton instance."""
    global _router
    if _router is None:
        _router = IntentRouter()
    return _router
