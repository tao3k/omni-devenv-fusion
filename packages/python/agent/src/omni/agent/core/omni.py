"""
agent/core/omni.py

CCA Loop implementation with Context Optimization (Token Diet).

This module provides the core OmniLoop class that orchestrates
conversation with smart context management.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, List, Optional, Literal
from dataclasses import dataclass, field

from omni.foundation.config.settings import get_setting
from omni.foundation.api.inference import InferenceEngine, Message

from .context.manager import ContextManager
from .context.pruner import PruningConfig


@dataclass
class OmniLoopConfig:
    """Configuration for the OmniLoop."""

    max_tokens: int = 128000
    retained_turns: int = 10
    auto_summarize: bool = False
    inference_model: str = "sonnet"


class OmniLoop:
    """
    Core conversation loop with smart context management.

    Features:
    - ContextManager for smart pruning
    - Turn tracking and statistics
    - Session isolation

    Usage:
        agent = OmniLoop()
        result = await agent.run("Your task here")
    """

    def __init__(self, config: OmniLoopConfig | None = None):
        """
        Initialize the OmniLoop.

        Args:
            config: Optional configuration. Uses defaults if None.
        """
        self.config = config or OmniLoopConfig()
        self.session_id: str = str(uuid.uuid4())[:8]
        self.step_count: int = 0

        # Initialize context manager with pruning config
        pruning_config = PruningConfig(
            max_tokens=self.config.max_tokens,
            retained_turns=self.config.retained_turns,
        )
        self.context = ContextManager(pruner=pruning_config)

        # Initialize inference engine
        self.engine = InferenceEngine(model=self.config.inference_model)

        # Session history (for backward compatibility with reporting)
        self.history: List[Dict[str, Any]] = []

        # Internal state
        _initialized = False

    async def _ensure_initialized(self):
        """Initialize system prompts once."""
        if not self._initialized:
            # Load system prompts from settings
            system_prompt = get_setting("omni.system_prompt", default="You are Omni-Dev Fusion.")
            self.context.add_system_message(system_prompt)
            self._initialized = True

    async def run(self, task: str, max_steps: int | None = None) -> str:
        """
        Execute a task through the CCA loop.

        Args:
            task: The task description.
            max_steps: Maximum steps (None = auto-estimate).

        Returns:
            The final result/response.
        """
        await self._ensure_initialized()

        # Add user task
        self.context.add_user_message(task)

        # Get initial context
        messages = self.context.get_active_context()

        # Simple loop: for now, just one inference
        # Future: Multi-step planning with tool use
        response = await self.engine.complete(messages=messages)

        # Update assistant response
        self.context.update_last_assistant(response.content)

        # Track for reporting
        self.history.extend(
            [
                {"role": "user", "content": task},
                {"role": "assistant", "content": response.content},
            ]
        )

        return response.content

    async def interactive_mode(self):
        """Run in interactive REPL mode."""
        await self._ensure_initialized()

        console_print = get_setting("omni.console.print", default=print)

        while True:
            try:
                user_input = input("\n[You] ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "q"):
                    break

                # Add user message
                self.context.add_user_message(user_input)

                # Get pruned context
                messages = self.context.get_active_context()

                # Get AI response
                response = await self.engine.complete(messages=messages)

                # Update context
                self.context.update_last_assistant(response.content)

                # Track history
                self.history.extend(
                    [
                        {"role": "user", "content": user_input},
                        {"role": "assistant", "content": response.content},
                    ]
                )

                # Print response
                console_print(f"\n[AI] {response.content}")

            except KeyboardInterrupt:
                break
            except EOFError:
                break

    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        return {
            "session_id": self.session_id,
            "step_count": self.step_count,
            "turn_count": self.context.turn_count,
            "context_stats": self.context.stats(),
        }

    def snapshot(self) -> Dict[str, Any]:
        """Create a serializable snapshot of the current session."""
        return {
            "session_id": self.session_id,
            "step_count": self.step_count,
            "context": self.context.snapshot(),
            "history": self.history,
        }
