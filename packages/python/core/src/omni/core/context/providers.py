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

    async def provide(self, state: dict[str, Any], budget: int) -> ContextResult:
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

    async def provide(self, state: dict[str, Any], budget: int) -> ContextResult:
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
    """Layer 2: Available tools index from Rust Scanner (filtered to core commands only)."""

    def __init__(self) -> None:
        self._index: list[dict] | None = None
        self._filtered_tools: set[str] | None = None

    async def provide(self, state: dict[str, Any], budget: int) -> ContextResult:
        # Load tools index (lazy)
        if self._index is None:
            from omni.core.skills.index_loader import SkillIndexLoader
            from omni.core.config.loader import load_filter_commands

            loader = SkillIndexLoader()
            # Must call _ensure_loaded() to populate _metadata_map
            loader._ensure_loaded()
            self._index = [{"name": name, **meta} for name, meta in loader._metadata_map.items()]

            # Cache filtered commands
            filter_config = load_filter_commands()
            self._filtered_tools = set(filter_config.commands)

        if not self._index:
            return ContextResult(content="", token_count=0, name="tools", priority=20)

        # Build lightweight summary with tools (filtering out filtered commands)
        summary_parts = ["<available_tools>"]
        for skill in self._index[:15]:  # Limit to top 15 skills
            skill_name = skill.get("name", "unknown")
            desc = skill.get("description", "")[:80]

            # List key tools for each skill (filter out filtered commands)
            tools = skill.get("tools", [])
            filtered_tool_names = []
            for t in tools[:10]:  # Check more tools to find 5 non-filtered
                tool_name = t.get("name", "")
                if tool_name and tool_name not in self._filtered_tools:
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
    """Layer 4: RAG-based knowledge retrieval."""

    async def provide(self, state: dict[str, Any], budget: int) -> ContextResult:
        # Skip if budget too small
        if budget < 500:
            return ContextResult(content="", token_count=0, name="rag", priority=40)

        messages = state.get("messages", [])
        query = state.get("current_task")
        if not query and messages:
            last_msg = messages[-1]
            # Handle both dict and object access patterns
            if isinstance(last_msg, dict):
                query = last_msg.get("content") or last_msg.get("text") or ""
            else:
                query = getattr(last_msg, "content", "") or getattr(last_msg, "text", "")

        if not query:
            return ContextResult(content="", token_count=0, name="rag", priority=40)

        # Placeholder: Integrate with vector store when available
        # For now, return empty context
        logger.debug("EpisodicMemoryProvider: Vector store not yet integrated")
        return ContextResult(content="", token_count=0, name="rag", priority=40)


__all__ = [
    "ActiveSkillProvider",
    "AvailableToolsProvider",
    "EpisodicMemoryProvider",
    "SystemPersonaProvider",
]
