# mcp-server/router.py
"""
The Cortex - Semantic Tool Routing System

Phase 14: The Telepathic Link (Mission Brief Protocol)
- Router (Orchestrator): Selects skills AND generates mission brief
- Hive Mind Cache: Instant routing for high-frequency queries
- Worker: Receives contextual mission briefing

Phase 14.5: The Semantic Cortex (Semantic Memory)
- VectorStore-based semantic caching for fuzzy matching
- "Fix the bug" and "Fix bug" now treated as SAME request
- Learning: Stores successful routing decisions in vector DB

Key Features:
- Prompt-based routing (Prompt is Policy)
- Mission Brief Protocol for context distillation
- Semantic cache with similarity threshold (0.85)
- Returns RoutingResult with skills, brief, and reasoning
"""
import json
import hashlib
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from common.mcp_core.inference import InferenceClient
from agent.core.skill_registry import get_skill_registry
from agent.core.vector_store import VectorMemory, get_vector_memory


# =============================================================================
# Phase 14: Routing Result with Mission Brief
# =============================================================================

@dataclass
class RoutingResult:
    """
    The complete output of the routing decision.

    Contains:
    - selected_skills: List of skill names to activate
    - mission_brief: Actionable directive for the Worker
    - reasoning: Audit trail of why these skills were chosen
    - confidence: Routing confidence (0.0-1.0)
    - from_cache: Whether this was a cache hit
    - timestamp: When routing decision was made
    """
    selected_skills: List[str]
    mission_brief: str
    reasoning: str
    confidence: float = 0.5
    from_cache: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skills": self.selected_skills,
            "mission_brief": self.mission_brief,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "from_cache": self.from_cache,
            "timestamp": self.timestamp,
        }


# =============================================================================
# Hive Mind Cache (LRU Cache for Zero-Latency Routing)
# =============================================================================

class HiveMindCache:
    """
    Simple LRU-style cache for routing decisions.

    Why?高频查询（如 "run tests", "commit", "check status"）
    不需要每次都调用 LLM。直接从缓存返回，延迟从 ~2s 降到 ~0ms。

    Features:
    - Exact match on query hash
    - Max size to prevent memory bloat
    - Time-based expiration (optional)
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.cache: Dict[str, RoutingResult] = {}
        self.max_size = max_size
        self.ttl = ttl_seconds

    def _hash_query(self, query: str) -> str:
        """Generate deterministic hash for query."""
        return hashlib.md5(query.encode()).hexdigest()

    def get(self, query: str) -> Optional[RoutingResult]:
        """Get cached routing result, returns None if not found or expired."""
        query_hash = self._hash_query(query)
        cached = self.cache.get(query_hash)

        if cached is None:
            return None

        # Check TTL
        if time.time() - cached.timestamp > self.ttl:
            del self.cache[query_hash]
            return None

        # Mark as cache hit and return
        cached.from_cache = True
        return cached

    def set(self, query: str, result: RoutingResult):
        """Cache a routing result."""
        query_hash = self._hash_query(query)

        # Evict oldest if at capacity
        if len(self.cache) >= self.max_size:
            # Remove first item (simple eviction)
            first_key = next(iter(self.cache))
            del self.cache[first_key]

        self.cache[query_hash] = result


# =============================================================================
# Phase 14.5: Semantic Cortex (Vector-Based Semantic Cache)
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

    # Similarity threshold: Lower = more fuzzy matching
    # 0.75 balances precision with practical fuzzy matching
    # 0.85+ = strict (may miss semantically similar queries)
    # 0.70+ = aggressive (may give irrelevant results)
    DEFAULT_SIMILARITY_THRESHOLD = 0.75

    # TTL for routing decisions (7 days in seconds)
    DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60

    def __init__(
        self,
        similarity_threshold: float = None,
        ttl_seconds: int = None,
    ):
        """
        Initialize Semantic Cortex.

        Args:
            similarity_threshold: Min similarity to return cached result (0.0-1.0)
            ttl_seconds: Time-to-live for routing decisions
        """
        self.similarity_threshold = similarity_threshold or self.DEFAULT_SIMILARITY_THRESHOLD
        self.ttl_seconds = ttl_seconds or self.DEFAULT_TTL_SECONDS
        self.vector_store: Optional[VectorMemory] = None
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
        """
        Recall similar routing decisions from semantic memory.

        Args:
            query: User query to search for

        Returns:
            RoutingResult if similar query found, None otherwise
        """
        if not self.vector_store:
            return None

        try:
            # Search for 1 most similar result
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
                # Entry expired, skip it
                return None

            if similarity >= self.similarity_threshold:
                # Found a match! Return cached routing result
                if "routing_result_json" in metadata:
                    import json
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
        """
        Store a routing decision in semantic memory.

        Args:
            query: The original user query
            result: The routing result to cache
        """
        if not self.vector_store:
            return

        try:
            import uuid
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, query))

            # ChromaDB metadata doesn't support dict, so serialize to JSON string
            import json

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

    async def cleanup_expired(self) -> int:
        """
        Remove expired routing decisions from the store.

        Returns:
            Number of expired entries removed
        """
        if not self.vector_store:
            return 0

        try:
            from chromadb.errors import NotFoundError

            # Get all entries (this is expensive, so limit to reasonable batch)
            results = await self.vector_store.search(
                query="",  # Empty query to get all
                n_results=100,  # Limit batch size
                collection=self.COLLECTION_NAME
            )

            removed = 0
            for entry in results:
                metadata = entry.metadata
                if "timestamp" in metadata and self._is_expired(metadata["timestamp"]):
                    try:
                        await self.vector_store.delete(
                            ids=[entry.id],
                            collection=self.COLLECTION_NAME
                        )
                        removed += 1
                    except NotFoundError:
                        pass  # Already deleted

            return removed
        except Exception as e:
            print(f"Warning: Semantic cleanup failed: {e}")
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the semantic cortex.

        Returns:
            Dict with entry_count, avg_similarity, threshold settings
        """
        if not self.vector_store:
            return {"error": "Vector store not available"}

        try:
            # Get collection count
            collections = await self.vector_store.list_collections()
            if self.COLLECTION_NAME not in collections:
                return {"entry_count": 0}

            # Get a sample to estimate stats
            results = await self.vector_store.search(
                query="",
                n_results=10,
                collection=self.COLLECTION_NAME
            )

            valid_entries = []
            for entry in results:
                if hasattr(entry, 'metadata') and "timestamp" in entry.metadata:
                    if not self._is_expired(entry.metadata["timestamp"]):
                        valid_entries.append(entry)

            return {
                "entry_count": len(valid_entries),
                "similarity_threshold": self.similarity_threshold,
                "ttl_seconds": self.ttl_seconds,
            }
        except Exception as e:
            return {"error": str(e)}


# =============================================================================
# Semantic Router with Mission Brief Protocol
# =============================================================================

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
        self.semantic_cortex = SemanticCortex() if use_semantic_cache else None

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

        Phase 14 Enhancement: Now includes mission_brief for Worker.
        Phase 14.5 Enhancement: Semantic Cortex for fuzzy matching.

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
        # Check first because it handles fuzzy semantics
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
- Focus on OUTCOME (e.g., "Fix indentation issues in router.py") not PROCESS (e.g., "Use grep to find, then read_file, then write")

GOOD Examples (Commander's Intent):
- "Fix the IndexError in router.py. Validate the fix with tests before committing."
- "Commit staged changes with message 'feat(api): add auth'. Show analysis first for confirmation."
- "Run the test suite and report results. If tests fail, identify the failing tests."

BAD Examples (Over-specified Steps):
- "First use filesystem to locate router.py, then use grep to find IndexError, then fix..."
- "Run pytest in tests/ directory, then if passed commit with message..."

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
            max_tokens=768,  # Slightly more for mission brief
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
            # Learn this routing decision for future semantic recall
            if self.semantic_cortex:
                await self.semantic_cortex.learn(user_query, routing_result)

            return routing_result

        except (json.JSONDecodeError, KeyError):
            return fallback


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


def clear_routing_cache():
    """Clear the Hive Mind Cache. Useful for debugging or after major changes."""
    router = get_router()
    router.cache.cache.clear()
