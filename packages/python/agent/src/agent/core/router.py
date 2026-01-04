# mcp-server/router.py
"""
The Cortex - Semantic Tool Routing System

Phase 14: The Telepathic Link (Mission Brief Protocol)
- Router (Orchestrator): Selects skills AND generates mission brief
- Hive Mind Cache: Instant routing for high-frequency queries
- Worker: Receives contextual mission briefing

Key Features:
- Prompt-based routing (Prompt is Policy)
- Mission Brief Protocol for context distillation
- LRU Cache for zero-latency routing on repeated queries
- Returns RoutingResult with skills, brief, and reasoning
"""
import json
import hashlib
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from common.mcp_core.inference import InferenceClient
from agent.core.skill_registry import get_skill_registry


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
# Semantic Router with Mission Brief Protocol
# =============================================================================

class SemanticRouter:
    """
    The Orchestrator's Brain: Routes requests and generates mission briefs.

    Phase 14 Enhancement:
    - Now generates mission_brief for context distillation
    - Hive Mind Cache for instant routing on repeated queries
    - Returns RoutingResult instead of raw dict
    """

    def __init__(
        self,
        inference_client: InferenceClient = None,
        cache_size: int = 1000,
        cache_ttl: int = 3600,
    ):
        self.registry = get_skill_registry()
        self.inference = inference_client or InferenceClient()
        self.cache = HiveMindCache(max_size=cache_size, ttl_seconds=cache_ttl)

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

        Args:
            user_query: The user's request
            chat_history: Optional conversation context
            use_cache: Whether to check cache first (default: True)

        Returns:
            RoutingResult with skills, mission_brief, reasoning, and metadata
        """
        # 🐝 Hive Mind Check: Instant routing for cached queries
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

MISSION BRIEF GUIDELINES:
- Be SPECIFIC and ACTIONABLE (not generic)
- Tell the Worker WHAT to do and WHY
- Include specific file paths or parameters if mentioned
- Example: "Fix the IndexError in src/main.py line 42. Use grep to locate, read_file to inspect, then write the fix."
- Example: "Commit the staged changes with message 'feat(api): add user auth'. First show analysis for confirmation."

OUTPUT FORMAT (JSON):
{{
    "skills": ["skill1", "skill2"],
    "mission_brief": "Actionable directive for the Worker...",
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

            # 🐝 Store in Hive Mind Cache
            self.cache.set(user_query, routing_result)

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
