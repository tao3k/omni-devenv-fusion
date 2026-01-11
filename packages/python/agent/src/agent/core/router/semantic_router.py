"""
src/agent/core/router/semantic_router.py
Semantic Router - Tool selection with Mission Brief Protocol.

Phase 14: Routes user requests to appropriate Skills.
Phase 14.5: Uses Semantic Cortex for fuzzy matching.
Phase 36.2: Virtual Loading via Vector Discovery (local skills only).

Usage:
    # SemanticRouter is defined in this file

    router = get_router()
    result = await router.route("Fix the bug in router.py")
"""

import json
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from agent.core.registry import get_skill_registry

from agent.core.router.models import RoutingResult

if TYPE_CHECKING:
    from common.mcp_core.inference.client import InferenceClient

# Lazy imports to avoid slow initialization
_cached_inference_client: Any = None
_cached_cache: Any = None
_cached_cortex: Any = None
_cached_vector_discovery: Any = None

# Lazy logger - defer structlog.get_logger() to avoid ~100ms import cost
_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily to avoid import-time overhead."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


def _get_vector_discovery() -> Any:
    """Get VectorSkillDiscovery lazily (Phase 36.2)."""
    global _cached_vector_discovery
    if _cached_vector_discovery is None:
        from agent.core.skill_discovery import VectorSkillDiscovery

        _cached_vector_discovery = VectorSkillDiscovery()
    return _cached_vector_discovery


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
        _cached_cortex = _LazySemanticCortex()
    return _cached_cortex


class _LazySemanticCortex:
    """Lazy wrapper for SemanticCortex - defers vector_store initialization."""

    COLLECTION_NAME = "routing_experience"
    DEFAULT_SIMILARITY_THRESHOLD = 0.75
    DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60

    def __init__(
        self,
        similarity_threshold: float = None,
        ttl_seconds: int = None,
    ):
        self.similarity_threshold = similarity_threshold or self.DEFAULT_SIMILARITY_THRESHOLD
        self.ttl_seconds = ttl_seconds or self.DEFAULT_TTL_SECONDS
        self._vector_store = None

    @property
    def vector_store(self) -> Any:
        """Lazy vector_store accessor."""
        if self._vector_store is None:
            from agent.core.vector_store import get_vector_memory

            try:
                self._vector_store = get_vector_memory()
            except Exception as e:
                _get_logger().warning("Could not initialize vector store", error=str(e))
                self._vector_store = None
        return self._vector_store

    @vector_store.setter
    def vector_store(self, value: Any) -> None:
        """Setter for backward compatibility with tests."""
        self._vector_store = value

    def _similarity_to_score(self, distance: float) -> float:
        return 1.0 - distance

    def _is_expired(self, timestamp_str: str) -> bool:
        try:
            timestamp = float(timestamp_str)
            return (time.time() - timestamp) > self.ttl_seconds
        except (ValueError, TypeError):
            return False

    async def recall(self, query: str) -> Optional[RoutingResult]:
        if not self.vector_store:
            return None

        try:
            results = await self.vector_store.search(
                query=query, n_results=1, collection=self.COLLECTION_NAME
            )

            if not results:
                return None

            best = results[0]
            similarity = self._similarity_to_score(best.distance)

            metadata = best.metadata
            if "timestamp" in metadata and self._is_expired(metadata["timestamp"]):
                return None

            if similarity >= self.similarity_threshold:
                if "routing_result_json" in metadata:
                    data = json.loads(metadata["routing_result_json"])
                    return RoutingResult(
                        selected_skills=data.get("skills", []),
                        mission_brief=data.get("mission_brief", ""),
                        reasoning=data.get("reasoning", ""),
                        confidence=data.get("confidence", 0.5),
                        from_cache=True,
                        timestamp=data.get("timestamp", time.time()),
                    )

            return None

        except Exception as e:
            _get_logger().warning("Semantic recall failed", error=str(e))
            return None

    async def learn(self, query: str, result: RoutingResult):
        if not self.vector_store:
            return

        try:
            import uuid

            doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, query))

            await self.vector_store.add(
                documents=[query],
                ids=[doc_id],
                collection=self.COLLECTION_NAME,
                metadatas=[
                    {
                        "routing_result_json": json.dumps(result.to_dict()),
                        "timestamp": str(result.timestamp),
                    }
                ],
            )
        except Exception as e:
            _get_logger().warning("Semantic learning failed", error=str(e))


# Backward compatibility alias
SemanticCortex = _LazySemanticCortex


class SemanticRouter:
    """
    The Orchestrator's Brain: Routes requests and generates mission briefs.

    Phase 14 Enhancement:
    - Now generates mission_brief for context distillation
    - Hive Mind Cache for instant routing on repeated queries
    - Returns RoutingResult instead of raw dict

    Phase 14.5 Enhancement:
    - Semantic Cortex: Vector-based fuzzy matching cache
    - "Fix bug" ≈ "Fix the bug" (same routing result)
    - Learns from past routing decisions

    Phase 36.2 Enhancement (Virtual Loading):
    - Cold Path: When LLM routing fails or is weak, search local skills only
    - Uses VectorSkillDiscovery to find relevant but unloaded local skills
    - Remote skills are NOT searched (installation not yet implemented)
    """

    def __init__(
        self,
        inference_client: "InferenceClient | None" = None,
        cache_size: int = 1000,
        cache_ttl: int = 3600,
        use_semantic_cache: bool = True,
        use_vector_fallback: bool = True,
    ):
        self.registry = get_skill_registry()
        self._inference = inference_client
        self._cache = None
        self._cache_config = (cache_size, cache_ttl)
        self._use_semantic_cache = use_semantic_cache
        self._use_vector_fallback = use_vector_fallback
        self._vector_discovery = None

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
        # Check if explicitly set (for tests)
        global _cached_cortex
        if _cached_cortex is not None:
            return _cached_cortex
        if not self._use_semantic_cache:
            return None
        return _get_semantic_cortex()

    @semantic_cortex.setter
    def semantic_cortex(self, value: Any) -> None:
        """Setter for backward compatibility with tests."""
        # Store in global cache to persist across property access
        global _cached_cortex
        _cached_cortex = value

    @property
    def vector_discovery(self) -> Any:
        """Lazy VectorSkillDiscovery accessor (Phase 36.2)."""
        if self._vector_discovery is None:
            self._vector_discovery = _get_vector_discovery()
        return self._vector_discovery

    @vector_discovery.setter
    def vector_discovery(self, value: Any) -> None:
        """Setter for backward compatibility with tests."""
        self._vector_discovery = value

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
        chat_history: List[Dict] = None,
        use_cache: bool = True,
    ) -> RoutingResult:
        """
        Analyze user query and return a complete RoutingResult.

        Cache Lookup Order:
        1. Semantic Cortex (fuzzy match): "Fix bug" ≈ "Fix the bug"
        2. Exact Match Cache (fast): "run tests" (exact string match)
        3. Vector Fallback (Phase 36.2): Search local skills for better matches

        Args:
            user_query: The user's request
            chat_history: Optional conversation context
            use_cache: Whether to check cache first (default: True)

        Returns:
            RoutingResult with skills, mission_brief, reasoning, and metadata
        """
        # 🧠 Phase 14.5: Semantic Cortex Check (Fuzzy Matching)
        if use_cache and self.semantic_cortex:
            recalled = await self.semantic_cortex.recall(user_query)
            if recalled is not None:
                return recalled

        # 🐝 Phase 14: Exact Match Cache (Fast, but rigid)
        if use_cache:
            cached = self.cache.get(user_query)
            if cached is not None:
                return cached

        menu_text = self._build_routing_menu()

        # Build context from chat history (last 3 exchanges)
        history_context = ""
        if chat_history:
            recent = chat_history[-6:]
            history_context = "\n".join(
                f"[{m.get('role', 'unknown')}]: {m.get('content', '')[:200]}" for m in recent
            )
            history_context = f"\n\nRECENT CONVERSATION:\n{history_context}"

        # 🚀 PROMPT > CODE: Routing logic AND mission brief generation
        system_prompt = f"""You are the Omni Orchestrator. Your job is to:
1. Route user requests to the right Skills (Workers)
2. Generate a concise MISSION BRIEF for the Worker

AVAILABLE SKILLS (WORKERS):
{menu_text}

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

MISSION BRIEF GUIDELINES (Commander's Intent - NOT Step-by-Step):
- Write COMMANDER'S INTENT: Tell the Worker WHAT goal to achieve and WHAT constraints to follow
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
            )

            # 🔥 Phase 36.2: Cold Path - Virtual Loading
            # If low confidence, fallback to generic skills, or weak route, try vector search
            is_weak_route = (
                not valid_skills  # No valid skills found
                or confidence < 0.5  # Low confidence
                or (
                    len(valid_skills) == 1 and valid_skills[0] in ["writer", "knowledge"]
                )  # Generic fallback
            )

            if is_weak_route and self._use_vector_fallback:
                await self._try_vector_fallback(user_query, routing_result)

            # 🐝 Store in Hive Mind Cache (Exact Match)
            self.cache.set(user_query, routing_result)

            # 🧠 Phase 14.5: Store in Semantic Cortex (Fuzzy Matching)
            if self.semantic_cortex:
                await self.semantic_cortex.learn(user_query, routing_result)

            return routing_result

        except (json.JSONDecodeError, KeyError):
            return fallback

    async def _try_vector_fallback(self, query: str, result: RoutingResult) -> None:
        """
        Phase 36.2: Search local skills via vector store for better routing.

        This is the "Cold Path" - used when LLM routing fails or is weak.
        Only searches LOCAL (installed) skills, not remote ones.

        Args:
            query: The user query
            result: RoutingResult to modify in-place
        """
        try:
            # Search local skills only (installed_only=True by default)
            suggestions = await self.vector_discovery.search(
                query=query,
                limit=3,
                installed_only=True,  # Only local skills
            )

            if not suggestions:
                return

            # Filter out already selected skills
            loaded_skills = set(result.selected_skills)
            new_candidates = [s for s in suggestions if s.get("id") not in loaded_skills]

            if not new_candidates:
                return

            # Found better local skills!
            top_skill = new_candidates[0]
            suggested_ids = [s.get("id") for s in new_candidates]

            # Update result with suggestions
            result.suggested_skills = suggested_ids
            result.reasoning += (
                f" [Vector Fallback] Found local skills: {', '.join(suggested_ids)}."
            )

            # Boost confidence since we found relevant skills
            result.confidence = max(result.confidence, 0.7)

            _get_logger().info(
                "Vector fallback triggered",
                query=query[:50],
                suggestions=suggested_ids,
            )

        except Exception as e:
            _get_logger().warning("Vector fallback failed", error=str(e))


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
