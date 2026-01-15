"""
agent/core/router/router.py
Phase 67: Adaptive Context - Intent-Driven Tool Loading

Router for intent-driven tool loading using hybrid search.

Features:
- Simple keyword extraction (no heavy NLP)
- Hybrid search (vector + keywords)
- Tool recommendation based on user intent
- Agent routing (HiveRouter compatibility)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


@dataclass
class AgentRoute:
    """Route decision for agent routing (HiveRouter compatibility)."""

    target_agent: str
    confidence: float = 1.0
    reasoning: str = ""
    task_brief: str = ""  # Mission brief string for the agent
    constraints: list[str] | None = None  # Optional constraints
    from_cache: bool = False


class IntentRouter:
    """
    Router for intent-driven tool loading using hybrid search.

    This class provides a simple interface for:
    - Extracting keywords from user queries
    - Searching tools using hybrid (vector + keyword) search
    - Ranking tools by relevance to intent
    """

    _instance: "IntentRouter | None" = None

    def __new__(cls, semantic_cortex: Any = None, **kwargs: Any) -> "IntentRouter":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, semantic_cortex: Any = None, **kwargs: Any) -> None:
        if self._initialized:
            return
        self._initialized = True
        # Store cortex for compatibility (unused in current implementation)
        self.cortex = semantic_cortex

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

    # =========================================================================
    # HiveRouter Compatibility Methods
    # =========================================================================

    # Agent personas for keyword-based routing (mimics old HiveRouter behavior)
    AGENT_PERSONAS: dict[str, dict[str, list[str]]] = {
        "coder": {
            "keywords": [
                "write",
                "code",
                "implement",
                "create",
                "add",
                "fix",
                "refactor",
                "modify",
                "develop",
            ],
            "skills": ["filesystem", "writer", "terminal"],
        },
        "reviewer": {
            "keywords": [
                "review",
                "test",
                "check",
                "audit",
                "verify",
                "git",
                "commit",
                "push",
                "branch",
            ],
            "skills": ["git", "testing"],
        },
        "orchestrator": {
            "keywords": [
                "plan",
                "explain",
                "help",
                "what",
                "how",
                "why",
                "describe",
                "context",
                "architecture",
            ],
            "skills": ["context"],
        },
    }

    # Cache for routing decisions
    _cache: dict[str, AgentRoute] = {}

    async def route_to_agent(
        self,
        query: str,
        context: str = "",
        use_cache: bool = True,
    ) -> AgentRoute:
        """
        Route a query to the appropriate agent based on keywords.

        This method provides HiveRouter compatibility by routing to:
        - "coder" for coding tasks (write, implement, fix, etc.)
        - "reviewer" for git/testing tasks (commit, test, review, etc.)
        - "orchestrator" for general/planning tasks

        Args:
            query: User query to route
            context: Additional context (unused, for compatibility)
            use_cache: Whether to use cached routing decisions

        Returns:
            AgentRoute with target_agent, confidence, and reasoning
        """
        # Check cache first
        cache_key = query.strip().lower()
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        # Try semantic routing first if cortex is available
        if self.cortex is not None:
            try:
                semantic_result = await self.cortex.recall(query)
                if semantic_result is not None:
                    # Use semantic routing result
                    selected_skills = getattr(semantic_result, "selected_skills", [])
                    semantic_confidence = getattr(semantic_result, "confidence", 0.9)

                    # Determine target agent based on selected skills
                    target_agent = self._skills_to_agent(selected_skills)

                    route = AgentRoute(
                        target_agent=target_agent,
                        confidence=semantic_confidence,
                        reasoning=f"Semantic match: {selected_skills}",
                        task_brief=query,  # Use the original query as mission brief
                        constraints=None,
                    )

                    if use_cache:
                        self._cache[cache_key] = route

                    return route
            except Exception as e:
                _get_logger().warning(
                    "Semantic routing failed, falling back to keywords", error=str(e)
                )

        # Fall back to keyword-based routing
        # Extract keywords from query (for potential future use)
        self.extract_keywords(query)
        query_lower = query.lower()

        # Score each agent based on keyword matching
        agent_scores: dict[str, float] = {}

        for agent, persona in self.AGENT_PERSONAS.items():
            score = 0.0
            reasoning_parts = []

            # Check keyword matches
            for kw in persona["keywords"]:
                if kw in query_lower:
                    score += 1.0
                    reasoning_parts.append(kw)

            agent_scores[agent] = score

            # Debug logging
            _get_logger().debug(
                "Agent scoring",
                agent=agent,
                score=score,
                matched_keywords=reasoning_parts,
            )

        # Determine winner
        if not agent_scores or all(s == 0 for s in agent_scores.values()):
            # Default to orchestrator for unclear queries
            target_agent = "orchestrator"
            confidence = 0.5
            reasoning = "No specific keywords matched, defaulting to orchestrator"
        else:
            # Find agent with highest score
            target_agent: str = max(agent_scores, key=agent_scores.get)  # type: ignore[arg-type]
            confidence = min(agent_scores[target_agent] / 3.0, 1.0)  # Normalize to 0-1
            matched = [
                kw for kw in self.AGENT_PERSONAS[target_agent]["keywords"] if kw in query_lower
            ]

            if target_agent == "coder":
                reasoning = f"Coding task: matched keywords {matched}"
            elif target_agent == "reviewer":
                reasoning = f"QA/Git task: matched keywords {matched}"
            else:
                reasoning = f"General/planning task: matched keywords {matched}"

        # Create route (use query as mission brief)
        route = AgentRoute(
            target_agent=target_agent,
            confidence=confidence,
            reasoning=reasoning,
            task_brief=query,
            constraints=None,
        )

        # Cache the result
        if use_cache:
            self._cache[cache_key] = route

        _get_logger().info(
            "Route decision",
            query=query[:50],
            target=target_agent,
            confidence=confidence,
        )

        return route

    def _skills_to_agent(self, skills: list[str]) -> str:
        """Convert selected skills to target agent."""
        # Map skills to agents based on skill categories
        skill_to_agent = {
            "git": "reviewer",
            "testing": "reviewer",
            "filesystem": "coder",
            "writer": "coder",
            "terminal": "coder",
        }

        for skill in skills:
            agent = skill_to_agent.get(skill.lower())
            if agent:
                return agent

        # Default to orchestrator if no mapping found
        return "orchestrator"

    def create_task_brief(
        self,
        query: str,
        target_agent: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a task brief for the target agent.

        Args:
            query: User query
            target_agent: Agent to route to
            context: Optional context dict with relevant_files, etc.

        Returns:
            Task brief dict with allowed_skills, etc.
        """
        allowed_skills = self.AGENT_PERSONAS.get(target_agent, {}).get("skills", [])

        brief: dict[str, Any] = {
            "task_description": query,
            "target_agent": target_agent,
            "allowed_skills": allowed_skills,
        }

        if context:
            if "relevant_files" in context:
                brief["relevant_files"] = context["relevant_files"]

        return brief

    def clear_cache(self) -> None:
        """Clear the routing cache."""
        self._cache.clear()
        _get_logger().debug("Routing cache cleared")


# Singleton accessor
_router: IntentRouter | None = None


def get_intent_router() -> IntentRouter:
    """Get the IntentRouter singleton instance."""
    global _router
    if _router is None:
        _router = IntentRouter()
    return _router
