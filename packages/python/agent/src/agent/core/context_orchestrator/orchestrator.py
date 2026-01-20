"""
orchestrator.py - ContextOrchestrator: The Async Conductor.

Orchestrates parallel retrieval of context layers with optional Skill Memory injection.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

import structlog

from .layers import (
    Layer1_SystemPersona,
    Layer2_AvailableSkills,
    Layer3_Knowledge,
    Layer4_AssociativeMemories,
    Layer5_Environment,
    Layer6_CodeMaps,
    Layer7_RawCode,
    Layer1_5_SkillMemory,
    ContextLayer,
)

logger = structlog.get_logger(__name__)

_ENCODER = None


def _get_encoder():
    """Lazy import tiktoken encoder."""
    global _ENCODER
    if _ENCODER is None:
        import tiktoken

        _ENCODER = tiktoken.get_encoding("cl100k_base")
    return _ENCODER


def _count_tokens(text: str) -> int:
    if not text:
        return 0
    encoder = _get_encoder()
    return len(encoder.encode(text))


class ContextOrchestrator:
    """
    The Async Conductor.
    Orchestrates retrieval of context layers in priority order.

    Supports dynamic insertion of Layer1_5_SkillMemory when skill prompts are provided.
    """

    def __init__(self, max_tokens: int = 128000, output_ratio: float = 0.2):
        self.max_tokens = max_tokens
        self.input_budget = int(max_tokens * (1 - output_ratio))

        # Initialize base layers in priority order (excluding Layer1_5)
        self._base_layers: List[ContextLayer] = [
            Layer1_SystemPersona(),  # System Persona (XML) - priority 1
            Layer2_AvailableSkills(),  # Available Skills (JSON) - priority 2
            Layer3_Knowledge(),  # Project Knowledge (Docs) - priority 3
            Layer4_AssociativeMemories(),  # Associative Memories (Vector) - priority 4
            Layer5_Environment(),  # Environment State (Sniffer) - priority 5
            Layer6_CodeMaps(),  # Code Maps (Tags) - priority 6
            Layer7_RawCode(),  # Raw Code (File) - priority 7
        ]

        logger.info(
            "ContextOrchestrator initialized",
            max_tokens=max_tokens,
            input_budget=self.input_budget,
            layers=len(self._base_layers),
        )

    def _build_layer_list(self, skill_prompts: Dict[str, str] | None) -> List[ContextLayer]:
        """
        Build the full layer list, optionally inserting Layer1_5.

        Args:
            skill_prompts: Optional dict of skill_name -> SKILL.md content

        Returns:
            List of layers in priority order
        """
        if not skill_prompts:
            return self._base_layers

        # Insert Layer1_5 after Layer1 (index 1)
        memory_layer = Layer1_5_SkillMemory(skill_prompts)
        return [self._base_layers[0], memory_layer] + self._base_layers[1:]

    async def build_prompt(
        self,
        task: str,
        history: List[dict[str, str]],
        skill_prompts: Dict[str, str] | None = None,
    ) -> str:
        """
        Builds the prompt by executing layers in sequence (respecting budget).

        Args:
            task: The current task description
            history: Conversation history
            skill_prompts: Optional skill prompts to inject via Layer1_5

        Returns:
            Assembled prompt string
        """
        current_budget = self.input_budget
        final_parts = []

        # Get layers (with optional Layer1_5 inserted)
        layers = self._build_layer_list(skill_prompts)

        logger.info(
            "ContextOrchestrator: Assembling context",
            task=task[:50],
            layers=len(layers),
            has_skill_memory=skill_prompts is not None,
        )

        for layer in layers:
            if current_budget <= 0:
                logger.info(f"Budget exhausted before layer {layer.name}")
                break

            try:
                content, used = await layer.assemble(task, history, current_budget)

                if content and used > 0:
                    final_parts.append(content)
                    current_budget -= used
                    logger.debug(f"Layer {layer.name} added {used} tokens")

            except Exception as e:
                logger.error(f"Layer {layer.name} crashed", error=str(e))

        prompt = "\n".join(final_parts)

        total_tokens = _count_tokens(prompt)
        logger.info(
            "Context assembled",
            total_tokens=total_tokens,
            budget_remaining=current_budget,
        )

        return prompt

    def get_context_stats(self, prompt: str) -> dict[str, Any]:
        """Get statistics about the assembled context."""
        count = _count_tokens(prompt)
        return {
            "total_tokens": count,
            "max_tokens": self.max_tokens,
            "utilization": count / self.max_tokens,
        }


# Singleton
_orchestrator: Optional[ContextOrchestrator] = None


def get_context_orchestrator(max_tokens: int = 128000) -> ContextOrchestrator:
    """Get the singleton ContextOrchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ContextOrchestrator(max_tokens)
    return _orchestrator


def build_context(task: str, history: List[dict[str, str]]) -> str:
    """
    Synchronous wrapper for legacy code.
    Use async build_prompt() for new code.
    """
    orch = get_context_orchestrator()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(orch.build_prompt(task, history))
    finally:
        if loop != asyncio.get_event_loop():
            loop.close()


__all__ = ["ContextOrchestrator", "get_context_orchestrator", "build_context"]
