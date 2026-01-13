"""
src/agent/core/router/semantic_router.py
Semantic Router - Tool selection with Mission Brief Protocol.

Phase 14: Routes user requests to appropriate Skills.
Phase 14.5: Uses Semantic Cortex for fuzzy matching.
Phase 36.2: Virtual Loading via Vector Discovery (local skills only).
Phase 37.3: Adaptive Confidence based on Score Gap.
Phase 41: Wisdom-Aware Routing - Inject past lessons from harvested knowledge.
Phase 42: State-Aware Routing - Inject environment state (Git, active context).

Usage:
    # SemanticRouter is defined in this file

    router = get_router()
    result = await router.route("Fix the bug in router.py")
"""

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from agent.core.registry import get_skill_registry

from agent.core.router.models import RoutingResult

if TYPE_CHECKING:
    from common.mcp_core.inference.client import InferenceClient

# [Phase 37.3] Adaptive confidence configuration
CONFIDENCE_HIGH_GAP = 0.15  # Gap > 15% = High confidence boost
CONFIDENCE_LOW_GAP = 0.05  # Gap < 5% = Low confidence penalty
CONFIDENCE_MAX_BOOST = 1.15  # Max boost multiplier for high distinctiveness
CONFIDENCE_MAX_PENALTY = 0.85  # Max penalty multiplier for ambiguity

# Lazy imports to avoid slow initialization
_cached_inference_client: Any = None
_cached_cache: Any = None
_cached_cortex: Any = None
_cached_vector_discovery: Any = None
_cached_librarian: Any = None  # [Phase 41] Lazy Librarian for wisdom retrieval
_cached_sniffer: Any = None  # [Phase 42] Lazy ContextSniffer for environment state

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


def _get_librarian() -> Any:
    """[Phase 41] Get Librarian function lazily for wisdom retrieval."""
    global _cached_librarian
    if _cached_librarian is None:
        from agent.capabilities.knowledge.librarian import consult_knowledge_base

        _cached_librarian = consult_knowledge_base
    return _cached_librarian


def _get_sniffer() -> Any:
    """[Phase 42] Get ContextSniffer lazily for environment state detection."""
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

    Phase 41 Enhancement (Wisdom-Aware Routing):
    - Injects past lessons from harvested knowledge into routing prompt
    - Consults Librarian for relevant lessons before generating Mission Brief
    - Mission Brief now includes operational wisdom from past mistakes

    Phase 42 Enhancement (State-Aware Routing):
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
        use_wisdom_routing: bool = True,  # [Phase 41] Enable wisdom-aware routing
    ):
        self.registry = get_skill_registry()
        self._inference = inference_client
        self._cache = None
        self._cache_config = (cache_size, cache_ttl)
        self._use_semantic_cache = use_semantic_cache
        self._use_vector_fallback = use_vector_fallback
        self._vector_discovery = None
        self._librarian = None  # [Phase 41] Lazy Librarian
        self._use_wisdom_routing = use_wisdom_routing
        self._sniffer = None  # [Phase 42] Lazy ContextSniffer

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

    @property
    def librarian(self) -> Any:
        """[Phase 41] Lazy Librarian accessor for wisdom retrieval."""
        if self._librarian is None:
            self._librarian = _get_librarian()
        return self._librarian

    @librarian.setter
    def librarian(self, value: Any) -> None:
        """Setter for backward compatibility with tests."""
        self._librarian = value

    @property
    def sniffer(self) -> Any:
        """[Phase 42] Lazy ContextSniffer accessor for environment state."""
        if self._sniffer is None:
            self._sniffer = _get_sniffer()
        return self._sniffer

    @sniffer.setter
    def sniffer(self, value: Any) -> None:
        """Setter for backward compatibility with tests."""
        self._sniffer = value

    def _format_lessons(self, knowledge_results: Dict[str, Any]) -> str:
        """[Phase 41] Format retrieved lessons for the routing prompt."""
        if not knowledge_results.get("success") or not knowledge_results.get("results"):
            return "No relevant past lessons found."

        lines = ["## Historical Lessons (Apply These):"]
        for i, result in enumerate(knowledge_results["results"][:3], 1):  # Top 3 lessons
            content = result.get("content", "")[:400]  # Truncate for prompt
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

        # [Phase 41+42] Parallel: Build menu, retrieve wisdom, AND sniff environment
        menu_task = asyncio.to_thread(self._build_routing_menu)
        knowledge_task = None
        sniffer_task = None

        if self._use_wisdom_routing:
            # [Phase 41] Retrieve relevant lessons from harvested knowledge
            knowledge_task = asyncio.create_task(
                self.librarian(
                    query=user_query,
                    n_results=3,  # Top 3 relevant lessons
                    domain_filter="harvested_insight",  # Only harvested insights
                )
            )

        # [Phase 42] Get environment state snapshot (parallel, non-blocking)
        sniffer_task = asyncio.create_task(self.sniffer.get_snapshot())

        # Wait for menu building (blocking, but fast)
        menu_text = await menu_task

        # [Phase 41] Get wisdom lessons (parallel, non-blocking)
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

        # [Phase 42] Get environment snapshot (parallel, non-blocking)
        env_snapshot = "Environment: Unknown"
        try:
            env_snapshot = await sniffer_task
        except Exception as e:
            _get_logger().warning("Environment sniffing failed", error=str(e))

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

[Phase 41] RELEVANT PAST LESSONS (Apply These):
{lessons_text}

[Phase 42] CURRENT ENVIRONMENT STATE:
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

[Phase 42] ENVIRONMENT-AWARE RULES:
- If user asks to "commit" and modified files are shown, include modified files in brief
- If workspace has uncommitted changes that might be relevant, acknowledge them in brief
- Use the git branch/status info to contextualize routing decisions

MISSION BRIEF GUIDELINES (Commander's Intent - NOT Step-by-Step):
- Write COMMANDER'S INTENT: Tell the Worker WHAT goal to achieve and WHAT constraints to follow
- REFERENCE relevant lessons from PAST LESSONS section in your brief
- [Phase 42] REFERENCE current ENVIRONMENT STATE when relevant (e.g., modified files, branch context)
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
            env_snapshot=env_snapshot,  # [Phase 42] Include environment snapshot
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
                env_snapshot=env_snapshot,  # [Phase 42] Include environment snapshot
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
        Phase 37.3: Adaptive Confidence based on Score Gap.

        This is the "Cold Path" - used when LLM routing fails or is weak.
        1. First search LOCAL (installed) skills
        2. If no local skills found, search REMOTE skills and return suggestions
        3. [Phase 37.3] Calculate adaptive confidence based on score gap

        Args:
            query: The user query
            result: RoutingResult to modify in-place
        """
        try:
            # 1. Search local skills first (installed_only=True by default)
            suggestions = await self.vector_discovery.search(
                query=query,
                limit=3,
                installed_only=True,  # Only local skills
            )

            # Filter out already selected skills
            loaded_skills = set(result.selected_skills)
            new_candidates = [s for s in suggestions if s.get("id") not in loaded_skills]

            # 2. If no local skills found, search remote skills for suggestions
            if not new_candidates:
                # Search remote skills (Phase 36.8: Auto-trigger skill.suggest logic)
                remote_suggestions = await self.vector_discovery.search(
                    query=query,
                    limit=5,
                    installed_only=False,  # Search all skills (remote too)
                )

                if remote_suggestions:
                    # Add remote suggestions to result
                    for skill in remote_suggestions:
                        if skill.get("id") not in loaded_skills:
                            result.remote_suggestions.append(
                                {
                                    "id": skill.get("id"),
                                    "name": skill.get("name"),
                                    "description": skill.get("description", ""),
                                    "keywords": skill.get("keywords", []),
                                    "score": skill.get("score", 0.0),
                                    "installed": skill.get("installed", False),
                                    "url": skill.get("url", ""),
                                }
                            )

                    result.reasoning += (
                        f" [Skill Suggestion] No local skills found. "
                        f"Found {len(remote_suggestions)} remote skill(s) that may help."
                    )
                    result.confidence = 0.3  # Low confidence, but providing suggestions

                    _get_logger().info(
                        "Auto-triggered skill suggestion",
                        query=query[:50],
                        suggestions=[s.get("id") for s in remote_suggestions],
                    )
                    return

            if not new_candidates:
                return

            # Found local skills!
            top_skill = new_candidates[0]
            suggested_ids = [s.get("id") for s in new_candidates]

            # Add newly discovered skills to selected_skills
            for skill_id in suggested_ids:
                if skill_id not in result.selected_skills:
                    result.selected_skills.append(skill_id)

            # Update result with suggestions
            result.suggested_skills = suggested_ids

            # [Phase 39] Build reasoning with boost details
            reasoning_parts = [f"Found relevant local skills: {', '.join(suggested_ids)}."]

            # Check for feedback influence
            feedback_bonus = top_skill.get("feedback_bonus", 0.0)
            keyword_boost = top_skill.get("keyword_bonus", 0.0)
            verb_matched = top_skill.get("verb_matched", False)

            if feedback_bonus > 0:
                reasoning_parts.append(f"(Reinforced by past success +{feedback_bonus:.2f})")
            elif feedback_bonus < 0:
                reasoning_parts.append(f"(Penalized by past rejection {feedback_bonus:.2f})")

            if keyword_boost > 0:
                if verb_matched:
                    reasoning_parts.append(
                        f"(Keyword match +{keyword_boost:.2f} with verb priority)"
                    )
                else:
                    reasoning_parts.append(f"(Keyword match +{keyword_boost:.2f})")

            result.reasoning += " [Vector Fallback] " + " ".join(reasoning_parts)

            # [Phase 37.3] Adaptive Confidence based on Score Gap
            # Calculate the gap between top and second result
            if len(new_candidates) >= 2:
                top_score = new_candidates[0].get("score", 0.0)
                second_score = new_candidates[1].get("score", 0.0)
                score_gap = top_score - second_score

                # Get raw score and keyword boost for debugging
                raw_vector = new_candidates[0].get("raw_vector_score", top_score)
                keyword_boost = new_candidates[0].get("keyword_boost", 0.0)

                if score_gap > CONFIDENCE_HIGH_GAP:
                    # High distinctiveness: boost confidence
                    # Example: 0.85 base score with 0.20 gap -> 0.95 (boosted)
                    boosted = min(CONFIDENCE_MAX_BOOST, 1.0 + (score_gap * 0.5))
                    result.confidence = min(0.95, top_score * boosted)
                    result.reasoning += (
                        f" [High Confidence] Score gap ({score_gap:.2f}) indicates strong match."
                    )
                    _get_logger().info(
                        "Adaptive confidence: high distinctiveness",
                        query=query[:50],
                        top_score=top_score,
                        second_score=second_score,
                        gap=score_gap,
                        final_confidence=result.confidence,
                    )
                elif score_gap < CONFIDENCE_LOW_GAP:
                    # Ambiguous match: penalize confidence
                    # Example: 0.80 base score with 0.02 gap -> 0.68 (penalized)
                    penalized = max(CONFIDENCE_MAX_PENALTY, 1.0 - (CONFIDENCE_LOW_GAP - score_gap))
                    result.confidence = max(0.3, top_score * penalized)
                    result.reasoning += (
                        f" [Low Confidence] Score gap ({score_gap:.2f}) indicates ambiguity."
                    )
                    _get_logger().info(
                        "Adaptive confidence: ambiguous match",
                        query=query[:50],
                        top_score=top_score,
                        second_score=second_score,
                        gap=score_gap,
                        final_confidence=result.confidence,
                    )
                else:
                    # Moderate gap: use base score
                    result.confidence = top_score
                    result.reasoning += f" [Moderate Confidence] Score gap: {score_gap:.2f}."

                # Log detailed scoring info
                _get_logger().debug(
                    "Vector search scoring details",
                    query=query[:50],
                    top_skill=top_skill.get("id"),
                    top_score=top_score,
                    raw_vector_score=raw_vector,
                    keyword_boost=keyword_boost,
                    second_score=second_score,
                    score_gap=score_gap,
                )
            else:
                # Only one result - use its score as base confidence
                result.confidence = new_candidates[0].get("score", 0.7)
                result.reasoning += " [Single Result] Only one relevant skill found."

            _get_logger().info(
                "Vector fallback triggered",
                query=query[:50],
                selected_skills=result.selected_skills,
                suggestions=suggested_ids,
                confidence=result.confidence,
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
