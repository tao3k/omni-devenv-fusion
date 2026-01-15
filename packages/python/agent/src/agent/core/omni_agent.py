"""
agent/core/omni_agent.py
CCA Runtime Loop (Omni Loop).

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

    Integrates all CCA components into a cohesive runtime.

    Components:
    - Conductor: ContextOrchestrator for layered context assembly
    - Librarian: VectorStore for semantic memory
    - Note-Taker: Session reflection and wisdom distillation
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
        self.max_steps: int = 1

        # The Conductor - Hierarchical Context Orchestration
        self.orchestrator: ContextOrchestrator = get_context_orchestrator()

        # The Note-Taker - Meta-cognitive reflection
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
        """Load all available tools from skills.

        Uses Rust scanner to discover @skill_script decorated functions
        and creates wrapper functions that use JIT loader for execution.
        """
        if self._tools:
            return  # Already loaded

        logger.info("OmniAgent: Loading tools...")

        # Try to load tools from Rust scanner
        try:
            import omni_core_rs
            from agent.core.skill_manager.jit_loader import (
                get_jit_loader,
                ToolRecord,
            )
            from common.skills_path import SKILLS_DIR

            # Check if scan_skill_tools is available
            if not hasattr(omni_core_rs, "scan_skill_tools"):
                raise AttributeError("scan_skill_tools not available in omni_core_rs")

            # Use SKILLS_DIR() to get the correct skills path from settings.yaml
            skills_path = str(SKILLS_DIR())
            rust_tools = omni_core_rs.scan_skill_tools(skills_path)

            if rust_tools:
                logger.info(f"Found {len(rust_tools)} tools from Rust scanner")
                loader = get_jit_loader()

                # Group tools by tool_name for deduplication
                seen = set()

                for rt in rust_tools:
                    tool_name = rt.tool_name
                    if tool_name in seen:
                        continue
                    seen.add(tool_name)

                    # Create a wrapper function for JIT execution
                    record = ToolRecord.from_rust(rt)

                    def make_wrapper(rec: ToolRecord):
                        async def wrapper(**kwargs):
                            return await loader.execute_tool(rec, kwargs)

                        return wrapper

                    wrapper_func = make_wrapper(record)

                    # Store as a callable with metadata
                    self._tools[tool_name] = wrapper_func

                    logger.debug(f"Loaded tool: {tool_name}")

                logger.info(f"Loaded {len(self._tools)} tools from Rust scanner")

        except (ImportError, AttributeError):
            logger.warning(
                "omni_core_rs not available or scan_skill_tools missing, falling back to registry"
            )

            # Fallback: Load from skill registry (legacy)
            from agent.core.registry import get_skill_tools

            skill_names = ["filesystem", "git", "testing", "memory"]
            for skill_name in skill_names:
                try:
                    tools = get_skill_tools(skill_name)
                    if tools:
                        self._tools.update(tools)
                        logger.debug(f"Loaded {len(tools)} tools from {skill_name}")
                except Exception as e:
                    logger.debug(f"Could not load tools from {skill_name}: {e}")

        # Generate tool schemas from JIT-loaded tools
        # This is needed because LLM client doesn't know about our Rust-scanned tools
        from agent.core.skill_manager.jit_loader import get_jit_loader

        loader = get_jit_loader()
        self._tool_schemas = []
        for tool_name, wrapper_func in self._tools.items():
            # Try to get the record from the wrapper's closure
            # The wrapper captures 'rec' which is a ToolRecord
            # We need to store the record for schema generation
            pass  # Schema generation happens below

        # Generate schemas for all tools we loaded
        # We need to re-scan to get the records for schema generation
        try:
            import omni_core_rs
            from common.skills_path import SKILLS_DIR

            skills_path = str(SKILLS_DIR())
            all_rust_tools = omni_core_rs.scan_skill_tools(skills_path)

            from agent.core.skill_manager.jit_loader import ToolRecord

            for rt in all_rust_tools:
                if rt.tool_name in self._tools:
                    record = ToolRecord.from_rust(rt)
                    schema = loader.get_tool_schema(record)
                    self._tool_schemas.append(schema)

            logger.info(f"Generated {len(self._tool_schemas)} tool schemas from Rust scanner")

        except Exception as e:
            logger.warning(f"Failed to generate tool schemas: {e}")
            self._tool_schemas = []

        logger.info(
            "OmniAgent: Tools loaded",
            tool_count=len(self._tools),
            schema_count=len(self._tool_schemas),
        )

    async def _build_cca_context(self, task: str) -> str:
        """
        [Step 4] The Conductor: Async Context Assembly.

        This assembles:
        - Layer 1: System Persona + Scratchpad
        - Layer 2: Available Skills (skill_index.json)
        - Layer 3: Project Knowledge (Docs)
        - Layer 4: Associative Memories (Vector Store)
        - Layer 5: Environment State (omni-sniffer)
        - Layer 6: Code Maps (omni-tags)
        - Layer 7: Raw Code Content (truncated)

        Returns:
            Complete context string for LLM
        """
        logger.info("OmniAgent: Building CCA context via Async Conductor...")

        # CHANGE: Added await for async build_prompt
        context = await self.orchestrator.build_prompt(
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

                # Handle async results FIRST before string conversion
                if asyncio.iscoroutine(result):
                    result = await result

                result_str = str(result) if result is not None else ""

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
        Decide: Call LLM with CCA context.

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
        Reflect: Trigger Note-Taker to distill wisdom.

        Analyzes the session trajectory and stores insights in Librarian.
        """
        logger.info("OmniAgent: Starting reflection (Note-Taker)...")

        if not self.history:
            return "No history to reflect on."

        # [FIX] Added await for async distill_and_save
        report = await self.note_taker.distill_and_save(self.history)
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
            max_steps: Maximum steps (default: 1)

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
                current_step = self.step_count + 1
                logger.info(
                    "OmniAgent: Step",
                    step=current_step,
                    total=self.max_steps,
                )

                # Observe + Orient: Build layered context (Step 4: Async)
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
                    logger.info("OmniAgent: Task completed", step=current_step)
                    break

                self.step_count += 1

            else:
                logger.warning("OmniAgent: Max steps reached", max_steps=self.max_steps)

            # Reflect: Distill wisdom
            reflection = await self._reflect()

            # Build final summary - actual steps executed = step_count + 1 (unless max reached)
            actual_steps = min(self.step_count + 1, self.max_steps)
            summary = f"""
## CCA Loop Complete

**Task:** {task}
**Steps:** {actual_steps}
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
    """Interactive CLI mode for OmniAgent with Dynamic Context Injection."""
    from rich.console import Console
    from agent.core.adaptive_loader import get_adaptive_loader

    console = Console()

    console.print(" CCA Runtime - Omni Loop")
    console.print("=" * 50)
    console.print("Type 'exit' or 'quit' to end the session.")
    console.print()

    # Initialize adaptive loader for dynamic tool loading
    loader = get_adaptive_loader()
    agent = OmniAgent()

    while True:
        try:
            user_input = input(" You: ").strip()
            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("\n Goodbye!")
                break
            if not user_input:
                continue

            # Dynamic Context Injection - Analyze intent & load relevant tools
            console.print("[dim]🧠 Analyzing intent & loading tools...[/dim]")

            active_tools = await loader.get_context_tools(user_input, dynamic_limit=15)

            # Debug: Show loaded tools (first 5)
            tool_names = [t.get("name", "unknown") for t in active_tools]
            console.print(
                f"[dim]🛠️  Active Tools ({len(tool_names)}): {', '.join(tool_names[:5])}...[/dim]"
            )

            # Run agent with dynamic tools
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
