"""
loop.py - CCA Loop Orchestration.

Main CCA Loop implementation combining ToolLoader, SkillInjector, and other components.
"""

from __future__ import annotations

import asyncio
import structlog
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = structlog.get_logger(__name__)


class OmniLoop:
    """
    CCA Loop Orchestrator - Combines all components into cohesive runtime.

    Components:
    - Conductor: ContextOrchestrator for layered context assembly
    - Librarian: VectorStore for semantic memory
    - Note-Taker: Session reflection and wisdom distillation
    - ToolLoader: Tools loaded from filesystem via Rust scanner
    - SkillInjector: Dynamic skill loading based on task intent

    CCA Loop:
        Observe -> Orient -> Decide -> Act -> Reflect (repeat)

    Usage:
        loop = OmniLoop()
        await loop.run("Fix the login bug in auth.py")
    """

    _instance: Optional["OmniLoop"] = None

    def __new__(cls) -> "OmniLoop":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        # Session state
        self.session_id: str = f"cca-{Path.cwd().name}-{id(self)}"
        self.history: List[Dict[str, str]] = []
        self.step_count: int = 0
        self.max_steps: int = 1

        # Components
        from agent.core.context_orchestrator import get_context_orchestrator
        from agent.core.note_taker import get_note_taker
        from agent.core.router import get_hive_router

        self.orchestrator = get_context_orchestrator()
        self.note_taker = get_note_taker()
        self.router = get_hive_router()

        # Tool and Skill management
        from agent.core.omni.tool_loader import get_tool_loader
        from agent.core.omni.skill_injector import get_skill_injector

        self.tool_loader = get_tool_loader()
        self.skill_injector = get_skill_injector()

        # LLM Client (lazy init)
        self._llm_client: Optional[Any] = None

        self._initialized = True
        logger.info(
            "OmniLoop initialized",
            session_id=self.session_id,
            max_steps=self.max_steps,
        )

    # =========================================================================
    # LLM Client
    # =========================================================================

    def _load_llm_client(self) -> Any:
        """Lazy load LLM client."""
        if self._llm_client is None:
            try:
                from common.mcp_core.inference import InferenceClient

                self._llm_client = InferenceClient()
                logger.info("OmniLoop: LLM client initialized (MiniMax via InferenceClient)")
            except Exception as e:
                logger.warning(f"OmniLoop: Failed to initialize LLM client: {e}")
                self._llm_client = None
        return self._llm_client

    # =========================================================================
    # Context Building
    # =========================================================================

    async def _build_cca_context(self, task: str) -> str:
        """
        [Step 4] The Conductor: Async Context Assembly.

        Assembles layered context from ContextOrchestrator.
        """
        logger.info("OmniLoop: Building CCA context via Async Conductor...")

        context = await self.orchestrator.build_prompt(
            task=task,
            history=self.history,
        )

        stats = self.orchestrator.get_context_stats(context)
        logger.info(
            "OmniLoop: Context built",
            total_tokens=stats["total_tokens"],
            utilization=f"{stats['utilization']:.1%}",
        )

        return context

    # =========================================================================
    # LLM Reasoning
    # =========================================================================

    async def _llm_reason(self, task: str, system_context: str) -> Dict[str, Any]:
        """
        Decide: Call LLM with CCA context.
        """
        client = self._load_llm_client()
        if client is None:
            return {
                "content": "Error: LLM client not available. Please configure inference settings.",
                "tool_calls": [],
            }

        # Build user query with recent history context
        recent_history = self.history[-10:] if self.history else []
        history_text = ""
        if recent_history:
            lines = []
            for msg in recent_history:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:200]
                lines.append(f"[{role.upper()}] {content}")
            history_text = "\n".join(lines)

        user_query = f"""
## Task
{task}

## Recent Conversation
{history_text}

## Instructions
Think step by step. If you need to take action, use the available tools.
When the task is complete, output: TASK_COMPLETE
"""

        result = await client.complete(
            system_prompt=system_context,
            user_query=user_query,
            tools=self.tool_loader.schemas if self.tool_loader.schemas else None,
            max_tokens=8192,
        )

        return result

    # =========================================================================
    # Reflection
    # =========================================================================

    async def _reflect(self) -> str:
        """
        Reflect: Trigger Note-Taker to distill wisdom.
        """
        logger.info("OmniLoop: Starting reflection (Note-Taker)...")

        if not self.history:
            return "No history to reflect on."

        report = await self.note_taker.distill_and_save(self.history)
        logger.info("OmniLoop: Reflection complete", report=report)

        return report

    # =========================================================================
    # Completion Check
    # =========================================================================

    def _is_complete(self, response_content: str) -> bool:
        """Check if task is complete."""
        complete_markers = ["TASK_COMPLETE", "DONE", "All done"]
        response_upper = response_content.upper()
        return any(marker.upper() in response_upper for marker in complete_markers)

    # =========================================================================
    # Main Loop
    # =========================================================================

    async def run(self, task: str, max_steps: Optional[int] = None) -> str:
        """
        Execute the CCA Runtime Loop.

        Args:
            task: The user's task description
            max_steps: Maximum steps (default: 1)

        Returns:
            Final result or summary
        """
        self.max_steps = max_steps or self.max_steps
        self.step_count = 0
        self.history = []

        logger.info(
            "OmniLoop: Starting CCA Loop",
            task_preview=task[:100],
            max_steps=self.max_steps,
        )

        # Add initial task to history
        self.history.append({"role": "user", "content": task})

        # Load tools
        self.tool_loader.load_tools()

        # Dynamic Skill Injection based on Task Intent
        await self.skill_injector.inject_for_task(task)

        try:
            while self.step_count < self.max_steps:
                current_step = self.step_count + 1
                logger.info(
                    "OmniLoop: Step",
                    step=current_step,
                    total=self.max_steps,
                )

                # Observe + Orient: Build layered context
                system_context = await self._build_cca_context(task)

                # Decide: LLM reasoning
                response = await self._llm_reason(task, system_context)
                content = response.get("content", "")
                tool_calls = response.get("tool_calls", [])

                # Add assistant response to history
                assistant_msg = {"role": "assistant", "content": content}
                self.history.append(assistant_msg)

                # Act: Execute tool calls
                if tool_calls:
                    logger.info(
                        "OmniLoop: Executing tools",
                        count=len(tool_calls),
                    )

                    for tool_call in tool_calls:
                        output = await self.tool_loader.execute_tool(tool_call)

                        # Add tool output to history
                        self.history.append(
                            {
                                "role": "tool",
                                "content": f"[Tool: {tool_call.get('name')}]\n{output}",
                                "tool_name": tool_call.get("name"),
                            }
                        )

                # Check for completion
                if self._is_complete(content):
                    logger.info("OmniLoop: Task completed", step=current_step)
                    break

                self.step_count += 1

            else:
                logger.warning("OmniLoop: Max steps reached", max_steps=self.max_steps)

            # Reflect: Distill wisdom
            reflection = await self._reflect()

            # Build final summary
            actual_steps = min(self.step_count + 1, self.max_steps)
            summary = f"""
## CCA Loop Complete

**Task:** {task}
**Steps:** {actual_steps}
**Reflection:** {reflection}
"""

            logger.info(
                "OmniLoop: Session complete",
                steps=self.step_count,
                history_len=len(self.history),
            )

            return summary

        except KeyboardInterrupt:
            logger.warning("OmniLoop: Interrupted by user")
            return "Task interrupted by user."

        except Exception as e:
            logger.error("OmniLoop: Runtime error", error=str(e))
            self.history.append(
                {
                    "role": "system",
                    "content": f"Runtime Error: {str(e)}",
                }
            )

            # Still try to reflect on the error
            try:
                await self._reflect()
            except:
                pass

            return f"Runtime Error: {str(e)}"


# =========================================================================
# Interactive Mode
# =========================================================================


async def interactive_mode():
    """Interactive CLI mode for OmniLoop with Dynamic Context Injection."""
    from rich.console import Console
    from agent.core.adaptive_loader import get_adaptive_loader

    console = Console()

    console.print(" CCA Runtime - Omni Loop")
    console.print("=" * 50)
    console.print("Type 'exit' or 'quit' to end the session.")
    console.print()

    # Initialize adaptive loader for dynamic tool loading
    loader = get_adaptive_loader()
    loop = OmniLoop()

    while True:
        try:
            user_input = input(" You: ").strip()
            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("\n Goodbye!")
                break
            if not user_input:
                continue

            # Dynamic Context Injection - Analyze intent & load relevant tools
            console.print("[dim] Analyzing intent & loading tools...[/dim]")

            active_tools = await loader.get_context_tools(user_input, dynamic_limit=15)

            # Debug: Show loaded tools (first 5)
            tool_names = [t.get("name", "unknown") for t in active_tools]
            console.print(
                f"[dim] Active Tools ({len(tool_names)}): {', '.join(tool_names[:5])}...[/dim]"
            )

            # Run loop with dynamic tools
            result = await loop.run(user_input)
            console.print(f"\n Agent: {result}")

        except KeyboardInterrupt:
            console.print("\n Interrupted. Goodbye!")
            break
        except Exception as e:
            console.print(f" Error: {e}")


# =========================================================================
# Sync Wrapper
# =========================================================================


def run_sync(task: str, max_steps: Optional[int] = None) -> str:
    """Synchronous wrapper for OmniLoop.run()."""
    loop = OmniLoop()
    return asyncio.run(loop.run(task, max_steps))


__all__ = ["OmniLoop", "interactive_mode", "run_sync"]
