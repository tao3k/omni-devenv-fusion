"""
src/agent/core/router/semantic_router.py
Semantic Router - Tool selection with Mission Brief Protocol.

Phase 14: Routes user requests to appropriate Skills.
Phase 14.5: Uses Semantic Cortex for fuzzy matching.

Usage:
    # SemanticRouter is defined in this file

    router = get_router()
    result = await router.route("Fix the bug in router.py")
"""
import json
import time
from typing import Dict, List, Optional

from common.mcp_core.inference import InferenceClient

from agent.core.skill_registry import get_skill_registry
from agent.core.vector_store import get_vector_memory

from agent.core.router.models import RoutingResult
from agent.core.router.cache import HiveMindCache


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
    """

    def __init__(
        self,
        inference_client: InferenceClient = None,
        cache_size: int = 1000,
        cache_ttl: int = 3600,
        use_semantic_cache: bool = True,
    ):
        self.registry = get_skill_registry()
        self.inference = inference_client or InferenceClient()
        self.cache = HiveMindCache(max_size=cache_size, ttl_seconds=cache_ttl)

        # Phase 14.5: Semantic Cortex for fuzzy matching
        self.semantic_cortex = None
        if use_semantic_cache:
            try:
                self.semantic_cortex = SemanticCortex()
            except Exception:
                pass  # Cortex unavailable, continue without it

    def _build_routing_menu(self) -> str:
        """Build routing menu from Skill Registry manifests (Data-Driven)."""
        menu_items = []
        for skill in self.registry.list_available_skills():
            manifest = self.registry.get_skill_manifest(skill)
            if manifest:
                keywords = manifest.routing_keywords if hasattr(manifest, 'routing_keywords') else []
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
                f"[{m.get('role', 'unknown')}]: {m.get('content', '')[:200]}"
                for m in recent
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
3. If the request is about writing, use 'writer' skill
4. If the request is about code structure analysis, use 'code_insight'
5. If the request is about file operations, use 'filesystem' or 'file_ops'
6. If the request is about testing, use 'testing' or 'testing_protocol'
7. If the request is about project knowledge/rules, use 'knowledge'
8. If the request is about git/version control, use 'git'
9. If the request is about terminal/shell commands, use 'terminal'
10. If the request is about general conversation, use 'writer' or 'knowledge'

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
            # Validate skills exist
            valid_skills = [s for s in skills if self.registry.get_skill_manifest(s)]

            if not valid_skills:
                return fallback

            routing_result = RoutingResult(
                selected_skills=valid_skills,
                mission_brief=routing_data.get(
                    "mission_brief",
                    f"Handle the user's request about: {user_query}"
                ),
                reasoning=routing_data.get(
                    "reasoning",
                    "Skill selected based on request analysis."
                ),
                confidence=routing_data.get("confidence", 0.5),
            )

            # 🐝 Store in Hive Mind Cache (Exact Match)
            self.cache.set(user_query, routing_result)

            # 🧠 Phase 14.5: Store in Semantic Cortex (Fuzzy Matching)
            if self.semantic_cortex:
                await self.semantic_cortex.learn(user_query, routing_result)

            return routing_result

        except (json.JSONDecodeError, KeyError):
            return fallback


# =============================================================================
# Semantic Cortex (Phase 14.5) - Moved here for organization
# =============================================================================

class SemanticCortex:
    """
    Vector-based semantic memory for routing decisions.

    Features:
    - Stores routing decisions as semantic embeddings
    - Fuzzy matching: "Fix bug" ≈ "Fix the bug"
    - Similarity threshold: Only return cached result if similarity > threshold
    - TTL support: Routing decisions expire after 7 days
    - Persistent storage across sessions

    Usage:
    1. Query: "Fix the bug in main.py"
    2. Search: Find similar historical queries
    3. If similarity > threshold: Return cached routing result
    4. If new: Store decision after LLM routing
    """

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
        self.vector_store = None
        self._init_vector_store()

    def _init_vector_store(self):
        """Initialize vector store connection."""
        try:
            self.vector_store = get_vector_memory()
        except Exception as e:
            print(f"Warning: Could not initialize vector store: {e}")
            self.vector_store = None

    def _similarity_to_score(self, distance: float) -> float:
        """Convert ChromaDB distance (0-1, lower is better) to similarity score (0-1, higher is better)."""
        return 1.0 - distance

    def _is_expired(self, timestamp_str: str) -> bool:
        """Check if a routing decision has expired based on its timestamp."""
        try:
            timestamp = float(timestamp_str)
            return (time.time() - timestamp) > self.ttl_seconds
        except (ValueError, TypeError):
            return False

    async def recall(self, query: str) -> Optional[RoutingResult]:
        """Recall similar routing decisions from semantic memory."""
        if not self.vector_store:
            return None

        try:
            results = await self.vector_store.search(
                query=query,
                n_results=1,
                collection=self.COLLECTION_NAME
            )

            if not results:
                return None

            best = results[0]
            similarity = self._similarity_to_score(best.distance)

            # Check if entry is expired
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
            print(f"Warning: Semantic recall failed: {e}")
            return None

    async def learn(self, query: str, result: RoutingResult):
        """Store a routing decision in semantic memory."""
        if not self.vector_store:
            return

        try:
            import uuid
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, query))

            await self.vector_store.add(
                documents=[query],
                ids=[doc_id],
                collection=self.COLLECTION_NAME,
                metadatas=[{
                    "routing_result_json": json.dumps(result.to_dict()),
                    "timestamp": str(result.timestamp),
                }]
            )
        except Exception as e:
            print(f"Warning: Semantic learning failed: {e}")


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
