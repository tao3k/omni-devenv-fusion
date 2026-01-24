"""
loop.py - Main OmniLoop Orchestrator

CCA Loop implementation with smart context management.
Integrates ReAct workflow with ContextManager for conversation handling.

Usage:
    from omni.agent.core.omni import OmniLoop, OmniLoopConfig

    loop = OmniLoop(kernel=kernel)
    result = await loop.run("Your task here")
"""

import asyncio
import uuid
from typing import Any

from omni.agent.core.context.manager import ContextManager
from omni.agent.core.context.pruner import ContextPruner, PruningConfig
from omni.foundation.config.settings import get_setting
from omni.foundation.services.llm import InferenceClient

from .config import OmniLoopConfig
from .react import ReActWorkflow
from .schemas import extract_tool_schemas

logger = None  # Set in __init__ after import


class OmniLoop:
    """
    Core conversation loop with smart context management.

    Features:
    - ContextManager for smart pruning
    - ReAct workflow for tool execution
    - Turn tracking and statistics
    - Session isolation

    Usage:
        agent = OmniLoop(kernel=kernel)
        result = await agent.run("Your task here")
    """

    def __init__(
        self,
        config: OmniLoopConfig | None = None,
        kernel: Any = None,
    ):
        """Initialize the OmniLoop.

        Args:
            config: Optional configuration. Uses defaults if None.
            kernel: Optional Kernel instance for tool execution.
        """
        self.config = config or OmniLoopConfig()
        self.session_id: str = str(uuid.uuid4())[:8]
        self.kernel = kernel

        # Initialize context manager with pruning config
        pruning_config = PruningConfig(
            max_tokens=self.config.max_tokens,
            retained_turns=self.config.retained_turns,
        )
        pruner = ContextPruner(config=pruning_config)
        self.context = ContextManager(pruner=pruner)

        # Initialize inference engine
        self.engine = InferenceClient()

        # Session history
        self.history: list[dict[str, Any]] = []

        # Internal state
        self._initialized: bool = False

    async def _ensure_initialized(self):
        """Initialize system prompts once."""
        if not self._initialized:
            system_prompt = get_setting("omni.system_prompt", default="You are Omni-Dev Fusion.")
            self.context.add_system_message(system_prompt)
            self._initialized = True

    async def _get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get tool schemas from kernel skill context with optimization.

        Applies:
        - filter_commands: Exclude commands from core tools
        - dynamic_tools limit: Cap number of tools
        - rerank_threshold: Re-rank by frequency if exceeded
        - schema_cache_ttl: Use cached schemas
        """
        from omni.core.cache.tool_schema import get_cached_schema, get_schema_cache
        from omni.core.config.loader import load_skill_limits

        if self.kernel and hasattr(self.kernel, "skill_context"):
            skill_context = self.kernel.skill_context
            limits = load_skill_limits()

            # Get core commands (filter_commands already applied)
            if limits.auto_optimize:
                # Use optimized core commands
                commands = skill_context.get_core_commands()

                # Apply dynamic_tools limit
                if len(commands) > limits.dynamic_tools:
                    # For now, just limit to dynamic_tools count
                    # In future, could use frequency-based ranking
                    commands = commands[: limits.dynamic_tools]

                # Apply rerank_threshold if exceeded (re-rank by frequency)
                all_commands = skill_context.list_commands()
                if len(all_commands) > limits.rerank_threshold:
                    # Use core commands first, then add from dynamic if needed
                    commands = skill_context.get_core_commands()
                    dynamic = skill_context.get_dynamic_commands()
                    # Combine: core + dynamic up to limit
                    commands = (commands + dynamic)[: limits.dynamic_tools]
            else:
                commands = skill_context.list_commands()

            # Use cached schema extraction
            def extract_schema(cmd: str) -> dict[str, Any]:
                handler = skill_context.get_command(cmd)
                if handler:
                    return extract_tool_schemas([cmd], lambda c: handler)[0]
                return {}

            # Get schemas with caching
            schemas = []
            cache = get_schema_cache()
            for cmd in commands:
                schema = get_cached_schema(cmd, lambda c=cmd: extract_schema(c))
                if schema:
                    schemas.append(schema)

            return schemas

        # Fallback: basic filesystem tools
        return self.engine.get_tool_schema(skill_names=["filesystem"])

    async def _execute_tool_call(self, tool_name: str, args: dict[str, Any]) -> str:
        """Execute a single tool call via kernel."""
        if self.kernel and hasattr(self.kernel, "execute_tool"):
            return await self.kernel.execute_tool(
                tool_name=tool_name,
                args=args,
                caller=None,  # OmniLoop has root privileges
            )

        # Direct execution via run_command
        from omni.core.skills.runtime import run_command

        return await run_command(tool_name, **args)

    def _get_react_workflow(self) -> ReActWorkflow:
        """Create ReAct workflow instance."""
        return ReActWorkflow(
            engine=self.engine,
            get_tool_schemas=self._get_tool_schemas,
            execute_tool=self._execute_tool_call,
            max_tool_calls=self.config.max_tool_calls,
            verbose=self.config.verbose,
        )

    async def run(self, task: str, max_steps: int | None = None) -> str:
        """Execute a task through the ReAct loop.

        ReAct Pattern:
        1. User asks task
        2. LLM decides to use tools (if needed)
        3. Execute tools and collect results
        4. LLM generates final response

        Args:
            task: The task description.
            max_steps: Maximum steps (None = use config max_tool_calls)

        Returns:
            The final result/response.
        """
        await self._ensure_initialized()

        # Add user task
        self.context.add_user_message(task)

        # Get context
        system_prompt = self.context.get_system_prompt() or "You are Omni-Dev Fusion."
        messages = self.context.get_active_context()

        # Run ReAct workflow
        workflow = self._get_react_workflow()
        response = await workflow.run(
            task=task,
            system_prompt=system_prompt,
            messages=messages,
        )

        # Update context
        self.context.update_last_assistant(response)

        # Track stats
        self.step_count = workflow.step_count
        self.tool_calls_count = workflow.tool_calls_count

        # Track history
        self.history.extend(
            [
                {"role": "user", "content": task},
                {"role": "assistant", "content": response},
            ]
        )

        # Trigger harvester in background (fire-and-forget)
        # This will detect skill creation requests and auto-generate skills
        asyncio.create_task(self._trigger_harvester())

        return response

    async def interactive_mode(self):
        """Run in interactive REPL mode."""
        from rich.console import Console

        from omni.foundation.config.settings import get_setting

        await self._ensure_initialized()

        console = Console()
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

                # Get context
                messages = self.context.get_active_context()
                system_prompt = self.context.get_system_prompt() or "You are Omni-Dev Fusion."

                # Run ReAct
                workflow = self._get_react_workflow()
                response = await workflow.run(
                    task=user_input,
                    system_prompt=system_prompt,
                    messages=messages,
                )

                # Update context
                self.context.update_last_assistant(response)

                # Track history
                self.history.extend(
                    [
                        {"role": "user", "content": user_input},
                        {"role": "assistant", "content": response},
                    ]
                )

                # Print response
                console_print(f"\n[AI] {response}")

            except KeyboardInterrupt:
                break
            except EOFError:
                break

        # Trigger harvester for self-evolution
        await self._trigger_harvester()

    async def _trigger_harvester(self):
        """
        Feature: Harvester Activation
        Detects skill creation requests in session history.
        Lightweight version - pattern detection only.
        Full auto-generation available via: omni skill generate "request"
        """
        if not self.history:
            return

        try:
            import importlib.util
            import sys

            from omni.foundation.config.skills import SKILLS_DIR

            factory_dir = SKILLS_DIR() / "skill" / "extensions" / "factory"
            harvester_path = factory_dir / "harvester.py"

            if not harvester_path.exists():
                return

            print(f"\n🌾 [Subconscious] Analyzing session {self.session_id}...")

            # Ensure factory_dir is in path for imports
            if str(factory_dir) not in sys.path:
                sys.path.insert(0, str(factory_dir))

            # Load harvester.py (lightweight, no MetaAgent dependencies)
            spec = importlib.util.spec_from_file_location("factory_harvester", harvester_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, "SkillHarvester"):
                    # Lightweight harvester without MetaAgent (detection only)
                    harvester = module.SkillHarvester(meta_agent=None)
                    await harvester.process_session(self.session_id, self.history)

        except Exception:
            # Subconscious failure should not affect main process exit
            pass

    def get_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        return {
            "session_id": self.session_id,
            "step_count": getattr(self, "step_count", 0),
            "turn_count": self.context.turn_count,
            "tool_calls": getattr(self, "tool_calls_count", 0),
            "context_stats": self.context.stats(),
        }

    def snapshot(self) -> dict[str, Any]:
        """Create a serializable snapshot of the current session."""
        return {
            "session_id": self.session_id,
            "step_count": getattr(self, "step_count", 0),
            "context": self.context.snapshot(),
            "history": self.history,
        }
