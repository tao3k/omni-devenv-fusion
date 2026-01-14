"""
agent/core/omni_agent.py
Phase 56: The Omni Loop (CCA Runtime Integration).

Integrates ContextOrchestrator, NoteTaker, and all Rust-accelerated tools
into a cohesive CCA runtime loop.

CCA Runtime Loop:
1. Observe (Layered Context): ContextOrchestrator builds perfect prompt
2. Orient (Recall): Auto-retrieve Hindsight and Skills from Librarian
3. Decide (Reasoning): LLM generates Thought and Action
4. Act (Execution): Execute Rust tools via ToolRegistry
5. Reflect (Post-Mortem): NoteTaker distills wisdom from trajectory

Usage:
    from agent.core.omni_agent import OmniAgent

    agent = OmniAgent()
    await agent.run("Fix the login bug in auth.py")
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from common.lib import setup_import_paths

# Setup paths before other imports
setup_import_paths()

from agent.core.context_orchestrator import (
    ContextOrchestrator,
    get_context_orchestrator,
)
from agent.core.note_taker import get_note_taker, NoteTaker
from agent.core.router import get_hive_router

logger = structlog.get_logger(__name__)


class OmniAgent:
    """
    The Omni Loop Agent - CCA Runtime Integration.

    Phase 56: Integrates all CCA components into a cohesive runtime.

    Components:
    - Conductor (Phase 55): ContextOrchestrator for layered context assembly
    - Librarian (Phase 53): VectorStore for semantic memory
    - Note-Taker (Phase 54): Session reflection and wisdom distillation
    - ToolRegistry: Skills loaded from filesystem

    CCA Loop:
        Observe -> Orient -> Decide -> Act -> Reflect (repeat)

    Usage:
        agent = OmniAgent()
        await agent.run("Refactor context_orchestrator.py")
    """

    _instance: Optional["OmniAgent"] = None

    def __new__(cls) -> "OmniAgent":
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
        self.max_steps: int = 20

        # [Phase 55] The Conductor - Hierarchical Context Orchestration
        self.orchestrator: ContextOrchestrator = get_context_orchestrator()

        # [Phase 54] The Note-Taker - Meta-cognitive reflection
        self.note_taker: NoteTaker = get_note_taker()

        # Hive Router for agent delegation
        self.router = get_hive_router()

        # Tool registry (skills)
        self._tools: Dict[str, Any] = {}
        self._tool_schemas: List[Dict] = []

        # LLM Client (lazy init)
        self._llm_client: Optional[Any] = None

        self._initialized = True
        logger.info(
            "OmniAgent initialized",
            session_id=self.session_id,
            max_steps=self.max_steps,
        )

    def _load_llm_client(self) -> Any:
        """Lazy load LLM client."""
        if self._llm_client is None:
            try:
                from common.mcp_core.inference import InferenceClient

                self._llm_client = InferenceClient()
                logger.info("OmniAgent: LLM client initialized (MiniMax via InferenceClient)")
            except Exception as e:
                logger.warning(f"OmniAgent: Failed to initialize LLM client: {e}")
                self._llm_client = None
        return self._llm_client

    def _load_tools(self) -> None:
        """Load all available tools from skills."""
        if self._tools:
            return  # Already loaded

        logger.info("OmniAgent: Loading tools from skill registry...")

        # Import here to avoid circular imports
        from agent.core.registry import get_skill_tools

        # Load tools from various skills
        skill_names = ["filesystem", "git", "testing", "memory"]
        for skill_name in skill_names:
            try:
                tools = get_skill_tools(skill_name)
                if tools:
                    self._tools.update(tools)
                    logger.debug(f"Loaded {len(tools)} tools from {skill_name}")
            except Exception as e:
                logger.debug(f"Could not load tools from {skill_name}: {e}")

        # Get tool schemas for LLM
        if self._llm_client:
            try:
                self._tool_schemas = self._llm_client.get_tool_schema()
            except Exception:
                self._tool_schemas = []

        logger.info(
            "OmniAgent: Tools loaded",
            tool_count=len(self._tools),
            schema_count=len(self._tool_schemas),
        )

    def _build_cca_context(self, task: str) -> str:
        """
        [Phase 55] The Conductor: Build layered context using ContextOrchestrator.

        This assembles:
        - Layer 1: System Persona + Scratchpad
        - Layer 2: Environment Snapshot (omni-sniffer)
        - Layer 3: Associative Memories (Librarian)
        - Layer 4: Code Maps (omni-tags)
        - Layer 5: Raw Code Content (truncated)

        Returns:
            Complete context string for LLM
        """
        logger.info("OmniAgent: Building CCA context via Conductor...")

        context = self.orchestrator.build_prompt(
            task=task,
            history=self.history,
        )

        stats = self.orchestrator.get_context_stats(context)
        logger.info(
            "OmniAgent: Context built",
            total_tokens=stats["total_tokens"],
            utilization=f"{stats['utilization']:.1%}",
        )

        return context

    async def _execute_tool(self, tool_call: Dict[str, Any]) -> str:
        """
        Execute a tool call from the LLM.

        Args:
            tool_call: Dict with 'name' and 'input' keys

        Returns:
            Tool execution result string
        """
        tool_name = tool_call.get("name", "unknown")
        tool_input = tool_call.get("input", {})

        logger.info(
            "OmniAgent: Executing tool",
            tool=tool_name,
            input_preview=str(tool_input)[:100],
        )

        # Find and execute the tool
        if tool_name in self._tools:
            try:
                tool_fn = self._tools[tool_name]
                result = tool_fn(**tool_input)
                result_str = str(result)

                # Handle async results
                if asyncio.iscoroutine(result):
                    result_str = await result

                logger.info(
                    "OmniAgent: Tool completed",
                    tool=tool_name,
                    result_preview=result_str[:100],
                )
                return result_str

            except Exception as e:
                error_msg = f"Tool '{tool_name}' failed: {str(e)}"
                logger.error("OmniAgent: Tool failed", tool=tool_name, error=str(e))
                return f"Error: {error_msg}"
        else:
            warning_msg = f"Unknown tool: {tool_name}"
            logger.warning("OmniAgent: Unknown tool", tool=tool_name)
            return f"Warning: {warning_msg}. Available tools: {list(self._tools.keys())}"

    async def _llm_reason(self, task: str, system_context: str) -> Dict[str, Any]:
        """
        [Phase 3] Decide: Call LLM with CCA context.

        Args:
            task: The user's task
            system_context: Layered context from ContextOrchestrator

        Returns:
            Dict with 'content' and 'tool_calls'
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
            tools=self._tool_schemas if self._tool_schemas else None,
            max_tokens=8192,
        )

        return result

    async def _reflect(self) -> str:
        """
        [Phase 5] Reflect: Trigger Note-Taker to distill wisdom.

        Analyzes the session trajectory and stores insights in Librarian.
        """
        logger.info("OmniAgent: Starting reflection (Note-Taker)...")

        if not self.history:
            return "No history to reflect on."

        report = self.note_taker.distill_and_save(self.history)
        logger.info("OmniAgent: Reflection complete", report=report)

        return report

    def _is_complete(self, response_content: str) -> bool:
        """Check if task is complete."""
        complete_markers = ["TASK_COMPLETE", "DONE", "All done"]
        response_upper = response_content.upper()
        return any(marker.upper() in response_upper for marker in complete_markers)

    async def run(self, task: str, max_steps: Optional[int] = None) -> str:
        """
        Execute the CCA Runtime Loop.

        Args:
            task: The user's task description
            max_steps: Maximum steps (default: 20)

        Returns:
            Final result or summary
        """
        self.max_steps = max_steps or self.max_steps
        self.step_count = 0
        self.history = []

        logger.info(
            "OmniAgent: Starting CCA Loop",
            task_preview=task[:100],
            max_steps=self.max_steps,
        )

        # Add initial task to history
        self.history.append({"role": "user", "content": task})

        # Load tools
        self._load_tools()

        try:
            while self.step_count < self.max_steps:
                logger.info(
                    "OmniAgent: Step",
                    step=self.step_count + 1,
                    total=self.max_steps,
                )

                # [Phase 1-2] Observe + Orient: Build layered context
                system_context = self._build_cca_context(task)

                # [Phase 3] Decide: LLM reasoning
                response = await self._llm_reason(task, system_context)
                content = response.get("content", "")
                tool_calls = response.get("tool_calls", [])

                # Add assistant response to history
                assistant_msg = {"role": "assistant", "content": content}
                self.history.append(assistant_msg)

                # [Phase 4] Act: Execute tool calls
                if tool_calls:
                    logger.info(
                        "OmniAgent: Executing tools",
                        count=len(tool_calls),
                    )

                    for tool_call in tool_calls:
                        output = await self._execute_tool(tool_call)

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
                    logger.info("OmniAgent: Task completed", step=self.step_count + 1)
                    break

                self.step_count += 1

            else:
                logger.warning("OmniAgent: Max steps reached", max_steps=self.max_steps)

            # [Phase 5] Reflect: Distill wisdom
            reflection = await self._reflect()

            # Build final summary
            summary = f"""
## CCA Loop Complete

**Task:** {task}
**Steps:** {self.step_count + 1}
**Reflection:** {reflection}
"""

            logger.info(
                "OmniAgent: Session complete",
                steps=self.step_count,
                history_len=len(self.history),
            )

            return summary

        except KeyboardInterrupt:
            logger.warning("OmniAgent: Interrupted by user")
            return "Task interrupted by user."

        except Exception as e:
            logger.error("OmniAgent: Runtime error", error=str(e))
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


async def interactive_mode():
    """Interactive CLI mode for OmniAgent."""
    from rich.console import Console

    console = Console()

    console.print(" CCA Runtime - Omni Loop (Phase 56)")
    console.print("=" * 50)
    console.print("Type 'exit' or 'quit' to end the session.")
    console.print()

    agent = OmniAgent()

    while True:
        try:
            user_input = input(" You: ").strip()
            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("\n Goodbye!")
                break
            if not user_input:
                continue

            result = await agent.run(user_input)
            console.print(f"\n Agent: {result}")

        except KeyboardInterrupt:
            console.print("\n Interrupted. Goodbye!")
            break
        except Exception as e:
            console.print(f" Error: {e}")


# Convenience function for sync usage
def run_sync(task: str, max_steps: Optional[int] = None) -> str:
    """Synchronous wrapper for OmniAgent.run()."""
    agent = OmniAgent()
    return asyncio.run(agent.run(task, max_steps))


__all__ = [
    "OmniAgent",
    "interactive_mode",
    "run_sync",
]
