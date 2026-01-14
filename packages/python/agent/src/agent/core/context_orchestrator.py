"""
agent/core/context_orchestrator.py
Phase 55: The Conductor - Hierarchical Context Orchestration.

Builds the "Perfect Prompt" using Rust primitives following CCA architecture.

Context Pyramid (Priority Order):
- Layer 1: System Persona + Scratchpad (High Priority, Immutable)
- Layer 2: Environment Snapshot (omni-sniffer) (Medium Priority)
- Layer 3: Associative Memories (omni-vector/Librarian) (Medium Priority)
- Layer 4: Code Maps (omni-tags) (Low Priority, High Volume)
- Layer 5: Raw Code Content (Lowest Priority, Truncated)

Philosophy:
- Smart token budgeting using tiktoken (direct, no PyO3 overhead)
- Dynamic recall from Librarian based on task relevance
- Map-first approach for code navigation
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
import tiktoken

from common.gitops import get_project_root
from common.skills_path import SKILLS_DIR, load_skill_module
from common.settings import get_setting

logger = structlog.get_logger(__name__)

# [Phase 57] Direct tiktoken - faster than Rust wrapper via PyO3
_ENCODER = tiktoken.get_encoding("cl100k_base")

# Lazy import for Rust-specific features (sniffer, outline, etc.)
# Initialized to None, set by _get_omni_core()
_omni_core_rs: Optional[Any] = None


def _get_omni_core() -> Any:
    """Get omni_core_rs module (lazy) for Rust-specific features."""
    global _omni_core_rs
    if _omni_core_rs is None:
        try:
            import omni_core_rs

            _omni_core_rs = omni_core_rs
            logger.debug("omni_core_rs loaded for Rust features")
        except ImportError:
            logger.debug("omni_core_rs not available")
            _omni_core_rs = None
    return _omni_core_rs


def _count_tokens(text: str) -> int:
    """Count tokens using direct tiktoken (faster than PyO3 wrapper)."""
    if not text:
        return 0
    return len(_ENCODER.encode(text))


def _truncate_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to fit token budget using direct tiktoken."""
    if not text:
        return ""
    tokens = _ENCODER.encode(text)
    if len(tokens) <= max_tokens:
        return text
    truncated = tokens[:max_tokens]
    return _ENCODER.decode(truncated)


class ContextLayer:
    """Base class for context layers."""

    name: str = "base"
    priority: int = 100  # Lower = higher priority

    def assemble(
        self,
        task: str,
        history: List[Dict[str, str]],
        budget: int,
    ) -> tuple[str, int]:
        """
        Assemble this layer's context.

        Args:
            task: Current task description
            history: Recent conversation history
            budget: Available tokens for this layer

        Returns:
            Tuple of (context_string, tokens_used)
        """
        raise NotImplementedError


class Layer1_SystemPersona(ContextLayer):
    """System Persona + Scratchpad - Immutable core."""

    name = "system_persona"
    priority = 1

    def assemble(
        self,
        task: str,
        history: List[Dict[str, str]],
        budget: int,
    ) -> tuple[str, int]:
        """Load system prompt and current scratchpad."""
        project_root = get_project_root()

        # Load system prompt
        system_prompt = ""
        prompt_path = project_root / "assets/prompts" / "system" / "main.md"
        if prompt_path.exists():
            system_prompt = prompt_path.read_text(encoding="utf-8")
        else:
            # Fallback to CLAUDE.md
            claude_path = project_root / "CLAUDE.md"
            if claude_path.exists():
                system_prompt = claude_path.read_text(encoding="utf-8")

        # Load scratchpad (current plan)
        scratchpad = ""
        scratchpad_path = project_root / "SCRATCHPAD.md"
        if scratchpad_path.exists():
            scratchpad = f"\n\n## Current Plan (SCRATCHPAD.md)\n{scratchpad_path.read_text(encoding='utf-8')}"

        content = f"{system_prompt}{scratchpad}"
        tokens = _count_tokens(content)

        return content, tokens


class Layer2_EnvironmentSnapshot(ContextLayer):
    """Environment snapshot from omni-sniffer."""

    name = "environment"
    priority = 2

    def assemble(
        self,
        task: str,
        history: List[Dict[str, str]],
        budget: int,
    ) -> tuple[str, int]:
        """Get environment snapshot from Rust omni-sniffer."""
        omni = _get_omni_core()
        if omni is None:
            return "", 0

        try:
            # Use Rust omni-sniffer for fast environment snapshot
            snapshot = omni.get_environment_snapshot(str(get_project_root()))
            content = f"\n\n## 🌍 Live Environment State\n{snapshot}\n"
            return content, _count_tokens(content)
        except Exception as e:
            logger.warning(f"Failed to get environment snapshot: {e}")
            return "", 0


class Layer3_AssociativeMemories(ContextLayer):
    """Memories from Librarian (omni-vector)."""

    name = "memories"
    priority = 3

    def assemble(
        self,
        task: str,
        history: List[Dict[str, str]],
        budget: int,
    ) -> tuple[str, int]:
        """Search Librarian for relevant memories and insights."""
        try:
            memory_skill = load_skill_module("memory")

            # Build query from task + recent history
            recent_context = ""
            if history:
                recent_msgs = [m.get("content", "") for m in history[-5:]]
                recent_context = " | ".join(recent_msgs[-3:])

            query = f"{task} | {recent_context}"

            # Search Librarian via Memory Skill
            # Layer3 needs async - we'll handle this at the orchestrator level
            # For now, skip memory layer if it requires async to avoid event loop issues
            logger.debug("Layer3: Skipping async memory search to avoid event loop conflicts")
            return "", 0

        except Exception as e:
            logger.warning(f"Failed to search memories: {e}")
            return "", 0


class Layer4_CodeMaps(ContextLayer):
    """Code outlines from omni-tags."""

    name = "code_maps"
    priority = 4

    def assemble(
        self,
        task: str,
        history: List[Dict[str, str]],
        budget: int,
    ) -> tuple[str, int]:
        """Get code outlines for relevant files."""
        omni = _get_omni_core()
        if omni is None:
            return "", 0

        try:
            project_root = get_project_root()
            content_parts = ["\n\n## 📁 Code Map (File Outlines)"]

            # Get current working directory context
            current_dir = project_root

            # Try to get outline of key files
            key_files = [
                project_root / "packages/python/agent/src/agent/main.py",
                project_root / "packages/python/agent/src/agent/core/orchestrator/core.py",
            ]

            for file_path in key_files:
                if file_path.exists():
                    outline = omni.get_file_outline(str(file_path))
                    if outline and "Error" not in outline:
                        rel_path = file_path.relative_to(project_root)
                        content_parts.append(f"\n### {rel_path}\n{outline}")

            # Add directory structure hint
            content_parts.append(f"\n### Project Root Structure\n`{project_root.name}/`")
            for item in sorted(project_root.iterdir())[:10]:
                if item.is_dir():
                    content_parts.append(f"  📁 {item.name}/")
                else:
                    content_parts.append(f"  📄 {item.name}")

            content = "\n".join(content_parts)
            return content, _count_tokens(content)

        except Exception as e:
            logger.warning(f"Failed to get code maps: {e}")
            return "", 0


class Layer5_RawCode(ContextLayer):
    """Raw code content - lowest priority, always truncated."""

    name = "raw_code"
    priority = 5

    def assemble(
        self,
        task: str,
        history: List[Dict[str, str]],
        budget: int,
    ) -> tuple[str, int]:
        """Get raw code content if budget allows."""
        omni = _get_omni_core()
        if omni is None or budget < 100:
            return "", 0

        try:
            # Read the most recently mentioned file in history
            if history:
                last_msg = history[-1].get("content", "")
                # Simple extraction - find paths like src/xxx.py
                import re

                paths = re.findall(r"([a-zA-Z0-9_/.-]+\.py)", last_msg)

                if paths:
                    file_path = Path(paths[0])
                    if not file_path.is_absolute():
                        file_path = get_project_root() / file_path

                    if file_path.exists():
                        content = file_path.read_text(encoding="utf-8")
                        # Truncate to remaining budget
                        truncated = _truncate_tokens(content, budget)
                        rel_path = file_path.relative_to(get_project_root())

                        added_note = ""
                        if len(truncated) < len(content):
                            added_note = f"\n\n[... Content truncated, {len(content) - len(truncated)} chars hidden ...]"

                        return (
                            f"\n\n## 💻 Active File: {rel_path}\n```{truncated}```{added_note}",
                            _count_tokens(truncated),
                        )

            return "", 0

        except Exception as e:
            logger.warning(f"Failed to read raw code: {e}")
            return "", 0


class ContextOrchestrator:
    """
    The Conductor - Orchestrates Hierarchical Context Assembly.

    Builds the "Perfect Prompt" by combining layers in priority order,
    respecting strict token budgets.

    Usage:
        orchestrator = ContextOrchestrator(max_tokens=128000)
        prompt = orchestrator.build_prompt(
            task="Fix the login bug",
            history=conversation_history
        )
    """

    def __init__(
        self,
        max_tokens: int = 128000,
        output_ratio: float = 0.2,
    ):
        """
        Initialize the Context Orchestrator.

        Args:
            max_tokens: Total context window size
            output_ratio: Ratio reserved for model output (default 20%)
        """
        self.max_tokens = max_tokens
        self.input_budget = int(max_tokens * (1 - output_ratio))

        # Initialize layers in priority order
        self.layers: List[ContextLayer] = [
            Layer1_SystemPersona(),
            Layer2_EnvironmentSnapshot(),
            Layer3_AssociativeMemories(),
            Layer4_CodeMaps(),
            Layer5_RawCode(),
        ]

        logger.info(
            "ContextOrchestrator initialized",
            max_tokens=max_tokens,
            input_budget=self.input_budget,
            layers=len(self.layers),
        )

    def build_prompt(
        self,
        task: str,
        history: List[Dict[str, str]],
    ) -> str:
        """
        Build the complete context prompt for the given task.

        Args:
            task: Current task description
            history: Recent conversation history

        Returns:
            Complete context string ready for LLM
        """
        budget = self.input_budget
        parts: List[str] = []

        logger.info(
            "Building context",
            task=task[:100],
            history_len=len(history),
            budget=budget,
        )

        for layer in self.layers:
            if budget <= 0:
                logger.debug(f"Layer {layer.name}: budget exhausted, skipping")
                break

            try:
                content, tokens = layer.assemble(task, history, budget)

                if content and tokens > 0:
                    parts.append(content)
                    budget -= tokens
                    logger.debug(f"Layer {layer.name}: +{tokens} tokens, {budget} remaining")

            except Exception as e:
                logger.warning(f"Layer {layer.name} failed: {e}")

        prompt = "\n".join(parts)

        # Log final stats
        total_tokens = _count_tokens(prompt)
        logger.info(
            "Context built",
            total_tokens=total_tokens,
            layers_used=len([p for p in parts if p]),
            budget_remaining=budget,
        )

        return prompt

    def get_context_stats(self, prompt: str) -> Dict[str, Any]:
        """Get statistics about the assembled context."""
        return {
            "total_tokens": _count_tokens(prompt),
            "max_tokens": self.max_tokens,
            "utilization": _count_tokens(prompt) / self.max_tokens,
        }


# Singleton accessor
_orchestrator: Optional[ContextOrchestrator] = None


def get_context_orchestrator(max_tokens: int = 128000) -> ContextOrchestrator:
    """Get the ContextOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ContextOrchestrator(max_tokens=max_tokens)
    return _orchestrator


def build_context(task: str, history: List[Dict[str, str]]) -> str:
    """
    Convenience function to build context for a task.

    Args:
        task: Current task description
        history: Recent conversation history

    Returns:
        Complete context string
    """
    return get_context_orchestrator().build_prompt(task, history)


__all__ = [
    "ContextOrchestrator",
    "ContextLayer",
    "get_context_orchestrator",
    "build_context",
    "Layer1_SystemPersona",
    "Layer2_EnvironmentSnapshot",
    "Layer3_AssociativeMemories",
    "Layer4_CodeMaps",
    "Layer5_RawCode",
]
