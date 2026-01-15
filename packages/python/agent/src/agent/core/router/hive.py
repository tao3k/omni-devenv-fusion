"""
src/agent/core/router/hive.py
Hive Router - Agent Delegation Routing.

 Enhancement:
- Routes requests to appropriate Specialist Agents (not just tools)
- Uses Semantic Cortex for fuzzy matching
- Integrates with SemanticRouter for backward compatibility

Usage:
    # HiveRouter is defined in this file

    router = get_hive_router()
    result = await router.route_to_agent("Fix the bug in main.py")
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel

from agent.core.router.models import AgentRoute, TaskBrief


class HiveRouter:
    """
    Intelligent Dispatcher for the Hive Swarm.

    Routing Strategy:
    1. Keyword Heuristics (Fast Path): Quick decision based on keywords
    2. Semantic Matching: Use Cortex for fuzzy query matching
    3. LLM Fallback: Use inference for ambiguous requests
    """

    # Agent personas for semantic matching
    AGENT_PERSONAS = {
        "coder": {
            "description": "Primary Executor. Writes code, refactors, fixes bugs, implements features.",
            "keywords": [
                "write",
                "create",
                "implement",
                "refactor",
                "fix",
                "edit",
                "modify",
                "add function",
                "new file",
            ],
            "skills": ["filesystem", "software_engineering", "terminal", "testing"],
        },
        "reviewer": {
            "description": "Quality Gatekeeper. Reviews changes, runs tests, checks git status, commits code.",
            "keywords": [
                "review",
                "check",
                "test",
                "verify",
                "commit",
                "git",
                "diff",
                "status",
                "run tests",
                "lint",
            ],
            "skills": ["git", "testing", "linter"],
        },
        "orchestrator": {
            "description": "The Manager. Plans tasks, explains concepts, manages context, handles ambiguity.",
            "keywords": [
                "plan",
                "explain",
                "how to",
                "what is",
                "analyze",
                "breakdown",
                "help",
                "understand",
                "context",
            ],
            "skills": ["context", "spec", "router", "knowledge"],
        },
    }

    def __init__(self, semantic_cortex=None):
        """
        Initialize Hive Router.

        Args:
            semantic_cortex: Optional SemanticCortex instance for fuzzy matching
        """
        self.cortex = semantic_cortex
        self._cache: Dict[str, AgentRoute] = {}

    async def route_to_agent(
        self, query: str, context: str = "", use_cache: bool = True
    ) -> AgentRoute:
        """
        Decide which agent should handle the user request.

        Args:
            query: The user's request
            context: Additional context (chat history, etc.)
            use_cache: Whether to use cached results

        Returns:
            AgentRoute with target agent and reasoning
        """
        # 1. Check cache
        cache_key = f"{query}:{context[:100]}" if context else query
        if use_cache and cache_key in self._cache:
            cached_route = self._cache[cache_key]
            #  Mark as from cache for UX display
            cached_route.from_cache = True
            return cached_route

        # 2. Keyword Heuristics (Fast Path)
        route = self._route_by_keywords(query)

        # 3. Semantic Matching (if Cortex available)
        if self.cortex:
            semantic_route = await self._route_by_semantics(query)
            if semantic_route.confidence > route.confidence:
                route = semantic_route

        # 4. Cache and return
        route.from_cache = False
        self._cache[cache_key] = route
        return route

    def _route_by_keywords(self, query: str) -> AgentRoute:
        """
        Fast path: Route based on keyword matching.

        Args:
            query: User query

        Returns:
            AgentRoute with keyword-based decision
        """
        query_lower = query.lower()

        # Check reviewer keywords first (more specific)
        reviewer_keywords = self.AGENT_PERSONAS["reviewer"]["keywords"]
        if any(kw in query_lower for kw in reviewer_keywords):
            return AgentRoute(
                target_agent="reviewer",
                confidence=0.75,
                reasoning=f"Keyword match: QA/Git operations detected in '{query}'",
                task_brief=query,
            )

        # Check coder keywords
        coder_keywords = self.AGENT_PERSONAS["coder"]["keywords"]
        if any(kw in query_lower for kw in coder_keywords):
            return AgentRoute(
                target_agent="coder",
                confidence=0.75,
                reasoning=f"Keyword match: Coding task detected in '{query}'",
                task_brief=query,
            )

        # Default to orchestrator (planning, clarification, or general tasks)
        return AgentRoute(
            target_agent="orchestrator",
            confidence=0.5,
            reasoning=f"Default: No specific keywords matched. Requires planning or clarification.",
            task_brief=query,
        )

    async def _route_by_semantics(self, query: str) -> AgentRoute:
        """
        Route using semantic similarity via Cortex.

        Args:
            query: User query

        Returns:
            AgentRoute with semantic-based decision
        """
        # Check cortex for similar past routing decisions
        cached_result = await self.cortex.recall(query)
        if cached_result:
            # Extract target from cached result
            skills = cached_result.selected_skills
            if "git" in skills or "testing" in skills:
                return AgentRoute(
                    target_agent="reviewer",
                    confidence=cached_result.confidence,
                    reasoning=f"Semantic match: Similar task was handled by reviewer (skills: {skills})",
                    task_brief=query,
                )
            elif "filesystem" in skills or "software_engineering" in skills:
                return AgentRoute(
                    target_agent="coder",
                    confidence=cached_result.confidence,
                    reasoning=f"Semantic match: Similar task was handled by coder (skills: {skills})",
                    task_brief=query,
                )

        # No semantic match found
        return AgentRoute(
            target_agent="orchestrator",
            confidence=0.4,
            reasoning="No semantic match found in cortex. Defaulting to orchestrator.",
            task_brief=query,
        )

    def create_task_brief(
        self, query: str, target_agent: str, context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a TaskBrief for agent handoff.

        Args:
            query: Original user query
            target_agent: Agent to receive the task
            context: Additional context

        Returns:
            TaskBrief dictionary
        """
        persona = self.AGENT_PERSONAS.get(target_agent, {})
        skills = persona.get("skills", [])

        return {
            "task_description": query,
            "constraints": [],
            "relevant_files": context.get("relevant_files", []) if context else [],
            "previous_attempts": [],
            "success_criteria": ["Complete the task as specified"],
            "target_agent": target_agent,
            "agent_description": persona.get("description", ""),
            "allowed_skills": skills,
        }

    def clear_cache(self):
        """Clear the routing cache."""
        self._cache.clear()


# =============================================================================
# Singleton
# =============================================================================

_hive_router_instance: Optional[HiveRouter] = None


def get_hive_router() -> HiveRouter:
    """Get or create HiveRouter singleton."""
    global _hive_router_instance
    if _hive_router_instance is None:
        # Try to get semantic cortex from main router
        try:
            from agent.core.router.semantic_router import get_router

            main_router = get_router()
            cortex = getattr(main_router, "semantic_cortex", None)
        except Exception:
            cortex = None
        _hive_router_instance = HiveRouter(semantic_cortex=cortex)
    return _hive_router_instance
