"""
providers.py - Concrete Context Providers

Layer-specific providers for the cognitive pipeline.
"""

from __future__ import annotations

from typing import Any, ClassVar

from omni.foundation.config.logging import get_logger

from .base import ContextProvider, ContextResult

logger = get_logger("omni.core.context.providers")


class SystemPersonaProvider(ContextProvider):
    """Layer 0: The immutable identity/persona."""

    DEFAULT_PERSONAS: ClassVar[dict[str, str]] = {
        "architect": "<role>You are a master software architect.</role>",
        "developer": "<role>You are an expert developer.</role>",
        "researcher": "<role>You are a thorough researcher.</role>",
    }

    def __init__(self, role: str = "architect") -> None:
        self.role = role
        self._content: str | None = None

    async def provide(self, state: dict[str, Any], budget: int) -> ContextResult | None:
        # Load persona content (cached)
        if self._content is None:
            self._content = self.DEFAULT_PERSONAS.get(
                self.role, f"<role>You are {self.role}.</role>"
            )

        token_count = len(self._content.split())  # Rough estimate
        return ContextResult(
            content=self._content,
            token_count=token_count,
            name="persona",
            priority=0,
        )


class ActiveSkillProvider(ContextProvider):
    """Layer 1.5: Active skill protocol (SKILL.md + required_refs)."""

    async def provide(self, state: dict[str, Any], budget: int) -> ContextResult | None:
        active_skill = state.get("active_skill")
        if not active_skill:
            return ContextResult(content="", token_count=0, name="active_skill", priority=10)

        # Load skill context from SkillMemory
        from omni.core.skills.memory import SkillMemory

        memory = SkillMemory()
        content = memory.hydrate_skill_context(active_skill)

        if not content or content.startswith("Error:"):
            logger.warning(f"ActiveSkillProvider: Failed to hydrate skill '{active_skill}'")
            return ContextResult(content="", token_count=0, name="active_skill", priority=10)

        # Wrap in XML for clearer LLM boundary
        xml_content = f"<active_protocol>\n{content}\n</active_protocol>"
        token_count = len(xml_content.split())

        logger.debug(
            f"ActiveSkillProvider: Loaded skill '{active_skill}'",
            tokens=token_count,
            chars=len(xml_content),
        )

        return ContextResult(
            content=xml_content,
            token_count=token_count,
            name="active_skill",
            priority=10,
        )


class AvailableToolsProvider(ContextProvider):
    """Layer 2: Available tools index from Rust Scanner (filtered to core commands only).

    Uses Arrow Analyzer for efficient tool context generation.
    Falls back to index-based approach if Arrow is unavailable.
    """

    def __init__(self) -> None:
        self._index: list[dict] | None = None
        self._filtered_tools: set[str] | None = None

    async def provide(self, state: dict[str, Any], budget: int) -> ContextResult | None:
        # Try Arrow Analyzer first for zero-copy optimization
        try:
            from omni.core.skills.analyzer import generate_system_context

            # Use Arrow Analyzer for high-performance context generation
            tools_context = generate_system_context(limit=50)

            if tools_context:
                content = f"<available_tools>\n{tools_context}\n</available_tools>"
                token_count = len(content.split())
                return ContextResult(
                    content=content,
                    token_count=token_count,
                    name="tools",
                    priority=20,
                )
        except Exception:
            pass  # Fall through to index-based approach

        # Fallback: Load tools index (lazy)
        if self._index is None:
            from omni.core.skills.index_loader import SkillIndexLoader

            # [FIX] Import is_filtered for pattern-based filtering
            from omni.core.config.loader import is_filtered

            loader = SkillIndexLoader()
            # Must call _ensure_loaded() to populate _metadata_map
            loader._ensure_loaded()
            self._index = [{"name": name, **meta} for name, meta in loader._metadata_map.items()]

        if not self._index:
            return ContextResult(content="", token_count=0, name="tools", priority=20)

        # Build lightweight summary with tools (filtering out filtered commands)
        summary_parts = ["<available_tools>"]

        # [FIX] Import is_filtered for usage in loop
        from omni.core.config.loader import is_filtered

        for skill in self._index[:15]:  # Limit to top 15 skills
            skill_name = skill.get("name", "unknown")
            desc = skill.get("description", "")[:80]

            # List key tools for each skill (filter out filtered commands)
            tools = skill.get("tools", [])
            filtered_tool_names = []
            for t in tools[:10]:  # Check more tools to find 5 non-filtered
                tool_name = t.get("name", "")
                # [FIX] Use is_filtered() pattern matcher instead of exact set lookup
                if tool_name and not is_filtered(tool_name):
                    filtered_tool_names.append(tool_name)
                if len(filtered_tool_names) >= 5:
                    break

            if filtered_tool_names:
                tools_str = ", ".join(filtered_tool_names)
                summary_parts.append(f"  - {skill_name}: {desc}")
                summary_parts.append(f"    Tools: {tools_str}")
            else:
                summary_parts.append(f"  - {skill_name}: {desc}")
        summary_parts.append("</available_tools>")

        content = "\n".join(summary_parts)
        token_count = len(content.split())

        return ContextResult(
            content=content,
            token_count=token_count,
            name="tools",
            priority=20,
        )


class EpisodicMemoryProvider(ContextProvider):
    """Layer 4: The Hippocampus (Long-term Memory Recall).

    Automatically retrieves relevant past interactions from VectorDB
    based on the current conversation context.

    This provider implements "Passive Recall" - it automatically searches
    for relevant memories before each agent step, solving the "forgetting" problem.
    """

    def __init__(self, top_k: int = 5, collection: str = "memory") -> None:
        """Initialize the episodic memory provider.

        Args:
            top_k: Number of memories to retrieve (default: 5).
            collection: VectorDB collection name for memories (default: "memory").
        """
        self.top_k = top_k
        self.collection = collection

    async def provide(self, state: dict[str, Any], budget: int) -> ContextResult | None:
        # Skip if budget too small (memories are low priority)
        if budget < 300:
            logger.debug("EpisodicMemoryProvider: Budget too small, skipping")
            return None

        messages = state.get("messages", [])
        query = state.get("current_task")

        # Fallback: use last message content as query
        if not query and messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                query = last_msg.get("content") or last_msg.get("text") or ""
            else:
                query = getattr(last_msg, "content", "") or getattr(last_msg, "text", "")

        if not query or len(query) < 5:
            logger.debug("EpisodicMemoryProvider: No valid query, skipping")
            return None

        try:
            # Import here to avoid circular dependencies
            from omni.foundation.services.vector import get_vector_store

            store = get_vector_store()

            # Perform vector search in the "memory" collection
            results = await store.search(
                query=query,
                n_results=self.top_k,
                collection=self.collection,
            )

            if not results:
                logger.debug("EpisodicMemoryProvider: No memories found")
                return None

            # Format memories for context
            memory_blocks = []
            for res in results:
                # res.metadata contains role, timestamp, step_index
                role = res.metadata.get("role", "unknown")
                timestamp = res.metadata.get("timestamp", 0)
                step_idx = res.metadata.get("step_index", -1)

                # Truncate long content
                content = res.content
                if len(content) > 300:
                    content = content[:300] + "..."

                # Format with metadata
                memory_blocks.append(f"[Past {role} (turn {step_idx})]: {content}")

            content = "<recalled_memories>\n" + "\n".join(memory_blocks) + "\n</recalled_memories>"

            # Estimate token count
            token_count = len(content.split())

            # Skip if still over budget
            if token_count > budget:
                logger.debug(
                    f"EpisodicMemoryProvider: Content over budget ({token_count} > {budget}), skipping"
                )
                return None

            logger.debug(
                f"EpisodicMemoryProvider: Retrieved {len(results)} memories",
                tokens=token_count,
            )

            return ContextResult(
                content=content,
                token_count=token_count,
                name="episodic_memory",
                priority=40,  # Lower than system/skill/tools, but above general chat
            )

        except ImportError as e:
            logger.warning(f"EpisodicMemoryProvider: Vector store not available ({e})")
            return None
        except Exception as e:
            logger.warning(f"EpisodicMemoryProvider: Search failed ({e})")
            return None


__all__ = [
    "ActiveSkillProvider",
    "AvailableToolsProvider",
    "EpisodicMemoryProvider",
    "SystemPersonaProvider",
]
