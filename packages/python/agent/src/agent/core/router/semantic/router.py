# agent/core/router/semantic/router.py
"""
Semantic Router - Tool selection with Mission Brief Protocol.

Routes user requests to appropriate Skills using:
- Semantic Cortex for fuzzy matching
- Virtual Loading via Vector Discovery (local skills only)
- Adaptive Confidence based on Score Gap
- Wisdom-Aware Routing - Inject past lessons from harvested knowledge
- State-Aware Routing - Inject environment state (Git, active context)
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from agent.core.skill_registry import get_skill_registry
from agent.core.router.models import RoutingResult

if TYPE_CHECKING:
    from common.mcp_core.inference.client import InferenceClient

# Lazy imports to avoid slow initialization
_cached_inference_client: Any = None
_cached_cache: Any = None
_cached_cortex: Any = None
_cached_vector_discovery: Any = None
_cached_librarian: Any = None
_cached_sniffer: Any = None
_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily to avoid import-time overhead."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


def _get_vector_discovery() -> Any:
    """Get SkillDiscovery lazily (Virtual Loading)."""
    global _cached_vector_discovery
    if _cached_vector_discovery is None:
        from agent.core.skill_discovery import SkillDiscovery

        _cached_vector_discovery = SkillDiscovery()
    return _cached_vector_discovery


def _get_librarian() -> Any:
    """Get Librarian function lazily for wisdom retrieval."""
    global _cached_librarian
    if _cached_librarian is None:
        from agent.capabilities.knowledge.librarian import consult_knowledge_base

        _cached_librarian = consult_knowledge_base
    return _cached_librarian


def _get_sniffer() -> Any:
    """Get ContextSniffer lazily for environment state detection."""
    global _cached_sniffer
    if _cached_sniffer is None:
        from agent.core.router.sniffer import get_sniffer

        _cached_sniffer = get_sniffer()
    return _cached_sniffer


def _get_inference_client() -> Any:
    """Get InferenceClient lazily to avoid loading anthropic SDK at init."""
    global _cached_inference_client
    if _cached_inference_client is None:
        from common.mcp_core.inference.client import InferenceClient

        _cached_inference_client = InferenceClient()
    return _cached_inference_client


def _get_cache(cache_size: int = 1000, cache_ttl: int = 3600) -> Any:
    """Get HiveMindCache lazily."""
    global _cached_cache
    cache_key = (cache_size, cache_ttl)
    if not hasattr(_cached_cache, "_cache_keys"):
        _cached_cache = {"_cache_keys": {}}
    if cache_key not in _cached_cache["_cache_keys"]:
        from agent.core.router.cache import HiveMindCache

        _cached_cache["_cache_keys"][cache_key] = HiveMindCache(
            max_size=cache_size, ttl_seconds=cache_ttl
        )
    return _cached_cache["_cache_keys"][cache_key]


def _get_semantic_cortex() -> Any:
    """Get SemanticCortex lazily."""
    global _cached_cortex
    if _cached_cortex is None:
        from agent.core.router.semantic.cortex import _LazySemanticCortex

        _cached_cortex = _LazySemanticCortex()
    return _cached_cortex


class SemanticRouter:
    """
    The Orchestrator's Brain: Routes requests and generates mission briefs.

    Semantic Routing Enhancement:
    - Now generates mission_brief for context distillation
    - Hive Mind Cache for instant routing on repeated queries
    - Returns RoutingResult instead of raw dict

    Semantic Cortex Enhancement:
    - Semantic Cortex: Vector-based fuzzy matching cache
    - "Fix bug" ≈ "Fix the bug" (same routing result)
    - Learns from past routing decisions

    Virtual Loading Enhancement:
    - Cold Path: When LLM routing fails or is weak, search local skills only
    - Uses VectorSkillDiscovery to find relevant but unloaded local skills
    - Remote skills are NOT searched (installation not yet implemented)

    Wisdom-Aware Routing Enhancement:
    - Injects past lessons from harvested knowledge into routing prompt
    - Consults Librarian for relevant lessons before generating Mission Brief
    - Mission Brief now includes operational wisdom from past mistakes

    State-Aware Routing Enhancement:
    - Injects real-time environment state into routing prompt
    - Uses ContextSniffer to detect Git status and active context
    - Prevents hallucinated actions by grounding routing in current reality
    """

    def __init__(
        self,
        inference_client: "InferenceClient | None" = None,
        cache_size: int = 1000,
        cache_ttl: int = 3600,
        use_semantic_cache: bool = True,
        use_vector_fallback: bool = True,
        use_wisdom_routing: bool = True,
    ):
        self.registry = get_skill_registry()
        self._inference = inference_client
        self._cache = None
        self._cache_config = (cache_size, cache_ttl)
        self._use_semantic_cache = use_semantic_cache
        self._use_vector_fallback = use_vector_fallback
        self._vector_discovery = None
        self._librarian = None
        self._use_wisdom_routing = use_wisdom_routing
        self._sniffer = None

    @property
    def inference(self) -> Any:
        """Lazy inference client accessor."""
        if self._inference is None:
            self._inference = _get_inference_client()
        return self._inference

    @inference.setter
    def inference(self, value: Any) -> None:
        """Setter for backward compatibility with tests."""
        self._inference = value

    @property
    def cache(self) -> Any:
        """Lazy cache accessor."""
        if self._cache is None:
            self._cache = _get_cache(*self._cache_config)
        return self._cache

    @cache.setter
    def cache(self, value: Any) -> None:
        """Setter for backward compatibility with tests."""
        self._cache = value

    @property
    def semantic_cortex(self) -> Any:
        """Lazy semantic cortex accessor."""
        global _cached_cortex
        if _cached_cortex is not None:
            return _cached_cortex
        if not self._use_semantic_cache:
            return None
        return _get_semantic_cortex()

    @semantic_cortex.setter
    def semantic_cortex(self, value: Any) -> None:
        """Setter for backward compatibility with tests."""
        global _cached_cortex
        _cached_cortex = value

    @property
    def vector_discovery(self) -> Any:
        """Lazy VectorSkillDiscovery accessor (Virtual Loading)."""
        if self._vector_discovery is None:
            self._vector_discovery = _get_vector_discovery()
        return self._vector_discovery

    @vector_discovery.setter
    def vector_discovery(self, value: Any) -> None:
        """Setter for backward compatibility with tests."""
        self._vector_discovery = value

    @property
    def librarian(self) -> Any:
        """Lazy Librarian accessor for wisdom retrieval."""
        if self._librarian is None:
            self._librarian = _get_librarian()
        return self._librarian

    @librarian.setter
    def librarian(self, value: Any) -> None:
        """Setter for backward compatibility with tests."""
        self._librarian = value

    @property
    def sniffer(self) -> Any:
        """Lazy ContextSniffer accessor for environment state."""
        if self._sniffer is None:
            self._sniffer = _get_sniffer()
        return self._sniffer

    @sniffer.setter
    def sniffer(self, value: Any) -> None:
        """Setter for backward compatibility with tests."""
        self._sniffer = value

    def _format_lessons(self, knowledge_results: Dict[str, Any]) -> str:
        """Format retrieved lessons for the routing prompt."""
        if not knowledge_results.get("success") or not knowledge_results.get("results"):
            return "No relevant past lessons found."

        lines = ["## Historical Lessons (Apply These):"]
        for i, result in enumerate(knowledge_results["results"][:3], 1):
            content = result.get("content", "")[:400]
            metadata = result.get("metadata", {})
            title = metadata.get("title", f"Lesson {i}")
            category = metadata.get("domain", "general")
            lines.append(f"\n### {title} [{category}]")
            lines.append(content)

        return "\n".join(lines)

    def _build_routing_menu(self) -> str:
        """Build routing menu from Skill Registry manifests (Data-Driven)."""
        menu_items = []
        for skill in self.registry.list_available_skills():
            manifest = self.registry.get_skill_manifest(skill)
            if manifest:
                keywords = (
                    manifest.routing_keywords if hasattr(manifest, "routing_keywords") else []
                )
                keywords_str = ", ".join(keywords[:8]) if keywords else "general"
                menu_items.append(
                    f"- [{skill}]: {manifest.description}\n  Keywords: {keywords_str}"
                )
        return "\n".join(menu_items)

    def _clean_json(self, text: str) -> str:
        """Clean JSON from LLM response, removing markdown code blocks."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    async def route(
        self,
        user_query: str,
        chat_history: List[Dict] | None = None,
        use_cache: bool = True,
    ) -> RoutingResult:
        """
        Analyze user query and return a complete RoutingResult.

        Cache Lookup Order:
        1. Semantic Cortex (fuzzy match): "Fix bug" ≈ "Fix the bug"
        2. Exact Match Cache (fast): "run tests" (exact string match)
        3. Vector Fallback (Virtual Loading): Search local skills for better matches

        Args:
            user_query: The user's request
            chat_history: Optional conversation context
            use_cache: Whether to check cache first (default: True)

        Returns:
            RoutingResult with skills, mission_brief, reasoning, and metadata
        """
        # Semantic Cortex Check (Fuzzy Matching)
        if use_cache and self.semantic_cortex:
            recalled = await self.semantic_cortex.recall(user_query)
            if recalled is not None:
                return recalled

        # Exact Match Cache (Fast, but rigid)
        if use_cache:
            cached = self.cache.get(user_query)
            if cached is not None:
                return cached

        # Parallel: Build menu, retrieve wisdom, AND sniff environment
        menu_task = asyncio.to_thread(self._build_routing_menu)
        knowledge_task = None
        sniffer_task = None

        if self._use_wisdom_routing:
            knowledge_task = asyncio.create_task(
                self.librarian(
                    query=user_query,
                    n_results=3,
                    domain_filter="harvested_insight",
                )
            )

        sniffer_task = asyncio.create_task(self.sniffer.get_snapshot())

        # Wait for menu building
        menu_text = await menu_task

        # Get wisdom lessons
        lessons_text = "No relevant past lessons found."
        if knowledge_task:
            try:
                knowledge_results = await knowledge_task
                lessons_text = self._format_lessons(knowledge_results)
                _get_logger().debug(
                    "Wisdom retrieved",
                    query=user_query[:50],
                    lessons_count=knowledge_results.get("count", 0),
                )
            except Exception as e:
                _get_logger().warning("Knowledge retrieval failed", error=str(e))
                lessons_text = "No relevant past lessons found."

        # Get environment snapshot
        env_snapshot = "Environment: Unknown"
        try:
            env_snapshot = await sniffer_task
        except Exception as e:
            _get_logger().warning("Environment sniffing failed", error=str(e))

        # Build context from chat history
        history_context = ""
        if chat_history:
            recent = chat_history[-6:]
            history_context = "\n".join(
                f"[{m.get('role', 'unknown')}]: {m.get('content', '')[:200]}" for m in recent
            )
            history_context = f"\n\nRECENT CONVERSATION:\n{history_context}"

        # Build and execute routing prompt
        system_prompt = self._build_system_prompt(menu_text, lessons_text, env_snapshot)
        user_message = f"""USER REQUEST: {user_query}{history_context}

Route this request and provide a mission brief."""

        result = await self.inference.complete(
            system_prompt=system_prompt,
            user_query=user_message,
            max_tokens=768,
        )

        # Build default fallback result
        fallback = RoutingResult(
            selected_skills=["writer", "knowledge"],
            mission_brief="Handle the user's general request. Ask for clarification if needed.",
            reasoning=f"Routing failed: {result.get('error', 'Unknown error')}. Using safe defaults.",
            confidence=0.0,
            env_snapshot=env_snapshot,
        )

        if not result["success"]:
            return fallback

        try:
            content = self._clean_json(result["content"])
            routing_data = json.loads(content)

            skills = routing_data.get("skills", [])
            confidence = routing_data.get("confidence", 0.5)

            # Validate skills exist
            valid_skills = [s for s in skills if self.registry.get_skill_manifest(s)]

            routing_result = RoutingResult(
                selected_skills=valid_skills if valid_skills else ["writer"],
                mission_brief=routing_data.get(
                    "mission_brief", f"Handle the user's request about: {user_query}"
                ),
                reasoning=routing_data.get(
                    "reasoning", "Skill selected based on request analysis."
                ),
                confidence=confidence,
                env_snapshot=env_snapshot,
            )

            # Cold Path - Virtual Loading
            is_weak_route = (
                not valid_skills
                or confidence < 0.5
                or (len(valid_skills) == 1 and valid_skills[0] in ["writer", "knowledge"])
            )

            if is_weak_route and self._use_vector_fallback:
                from agent.core.router.semantic.fallback import try_vector_fallback

                await try_vector_fallback(user_query, routing_result, self.vector_discovery)

            # Store in Hive Mind Cache (Exact Match)
            self.cache.set(user_query, routing_result)

            # Store in Semantic Cortex (Fuzzy Matching)
            if self.semantic_cortex:
                await self.semantic_cortex.learn(user_query, routing_result)

            return routing_result

        except (json.JSONDecodeError, KeyError):
            return fallback

    def _build_system_prompt(
        self,
        menu_text: str,
        lessons_text: str,
        env_snapshot: str,
    ) -> str:
        """Build the system prompt for routing."""
        return f"""You are the Omni Orchestrator. Your job is to:
1. Route user requests to the right Skills (Workers)
2. Generate a concise MISSION BRIEF for the Worker

AVAILABLE SKILLS (WORKERS):
{menu_text}

## RELEVANT PAST LESSONS (Apply These):
{lessons_text}

## CURRENT ENVIRONMENT STATE:
{env_snapshot}

ROUTING RULES:
1. Analyze the user's request and conversation context
2. Select the MINIMAL set of skills needed (usually 1-2, max 3)
3. If the request is about CREATING documentation (write docs, create README, write guide), use 'documentation' skill
4. If the request is about POLISHING/IMPROVING existing text (grammar, style, rewrite), use 'writer' skill
5. If the request is about code structure analysis, use 'code_insight'
6. If the request is about file operations, use 'filesystem' (includes grep, AST, batch operations)
7. If the request is about testing, use 'testing' or 'testing_protocol'
8. If the request is about project knowledge/rules, use 'knowledge'
9. If the request is about git/version control, use 'git'
10. If the request is about terminal/shell commands, use 'terminal'
11. If the request is about general conversation, use 'writer' or 'knowledge'

## ENVIRONMENT-AWARE RULES:
- If user asks to "commit" and modified files are shown, include modified files in brief
- If workspace has uncommitted changes that might be relevant, acknowledge them in brief
- Use the git branch/status info to contextualize routing decisions

MISSION BRIEF GUIDELINES (Commander's Intent - NOT Step-by-Step):
- Write COMMANDER'S INTENT: Tell the Worker WHAT goal to achieve and WHAT constraints to follow
- REFERENCE relevant lessons from PAST LESSONS section in your brief
- REFERENCE current ENVIRONMENT STATE when relevant (e.g., modified files, branch context)
- If a lesson mentions a pitfall, explicitly mention it in constraints
- AVOID step-by-step procedures: Let the Worker decide tool order based on context
- Be GENERAL and PATH-INDEPENDENT: This brief will be CACHED for future similar requests
- If user mentioned a file, note it but don't hardcode paths (file may move)
- Focus on OUTCOME (e.g., "Fix indentation issues in router.py") not PROCESS

GOOD Examples (Commander's Intent):
- "Fix the IndexError in router.py. Validate the fix with tests before committing."
- "Commit staged changes with message 'feat(api): add auth'. Show analysis first for confirmation."
- "Run the test suite and report results. If tests fail, identify the failing tests."

OUTPUT FORMAT (JSON):
{{
    "skills": ["skill1", "skill2"],
    "mission_brief": "Commander's intent for the Worker...",
    "confidence": 0.85,
    "reasoning": "Why these skills were chosen..."
}}

IMPORTANT: Return ONLY valid JSON, no markdown code blocks, no explanations."""


# =============================================================================
# Singleton
# =============================================================================

_router_instance: Optional[SemanticRouter] = None


def get_router() -> SemanticRouter:
    """Get or create SemanticRouter singleton."""
    global _router_instance
    if _router_instance is None:
        _router_instance = SemanticRouter()
    return _router_instance
