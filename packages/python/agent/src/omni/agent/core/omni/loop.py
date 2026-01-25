"""
loop.py - Main OmniLoop Orchestrator

CCA Loop implementation with smart context management.
Integrates ReAct workflow with ContextManager for conversation handling.

Features:
- CognitiveOrchestrator for dynamic system prompt building
- Meta-Cognition Protocol via RoutingGuidanceProvider
- Smart context pruning and management

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
from omni.core.context.orchestrator import create_omni_loop_context
from omni.foundation.config.logging import get_logger
from omni.foundation.config.settings import get_setting
from omni.foundation.services.llm import InferenceClient

from .config import OmniLoopConfig
from .react import ReActWorkflow
from .schemas import extract_tool_schemas

logger = get_logger("omni.agent.loop")


class OmniLoop:
    """
    Core conversation loop with smart context management.

    Features:
    - ContextManager for smart pruning
    - ReAct workflow for tool execution
    - CognitiveOrchestrator for dynamic system prompt (Meta-Cognition Protocol)
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

        # Initialize CognitiveOrchestrator for dynamic context building
        self.orchestrator = create_omni_loop_context()

        # Session history
        self.history: list[dict[str, Any]] = []

        # Internal state
        self._initialized: bool = False

    async def _ensure_initialized(self):
        """Initialize system prompts using CognitiveOrchestrator."""
        if not self._initialized:
            # Build dynamic context using CognitiveOrchestrator
            # This includes: Persona + Routing Protocol + Tools + Active Skill
            state = {"messages": [], "session_id": self.session_id}
            try:
                system_prompt = await self.orchestrator.build_context(state)
                logger.info(
                    "Context built for Omni-Loop",
                    tokens=len(system_prompt.split()),
                )
            except Exception as e:
                logger.error(f"Context build failed: {e}, using fallback")
                system_prompt = get_setting(
                    "omni.system_prompt",
                    default="You are Omni-Dev Fusion. Think before you act.",
                )

            self.context.add_system_message(system_prompt)
            self._initialized = True

    async def _get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get tool schemas from kernel skill context with optimization.

        Applies:
        - filter_commands: Exclude filtered commands (only core tools)
        - dynamic_tools limit: Cap number of tools
        - DISCOVERY_FIRST: Ensure skill.discover is first in the list

        Note: Dynamic commands (filtered) are NOT included in omni run.
        They can only be loaded on demand via dynamic loading.
        """
        from omni.core.cache.tool_schema import get_cached_schema
        from omni.core.config.loader import load_skill_limits

        if self.kernel and hasattr(self.kernel, "skill_context"):
            skill_context = self.kernel.skill_context
            limits = load_skill_limits()

            # Get core commands only (filter_commands applied, dynamic excluded)
            commands = skill_context.get_core_commands()

            # Apply dynamic_tools limit
            if len(commands) > limits.dynamic_tools:
                commands = commands[: limits.dynamic_tools]

            # Use cached schema extraction
            def extract_schema(cmd: str) -> dict[str, Any]:
                handler = skill_context.get_command(cmd)
                if handler:
                    return extract_tool_schemas([cmd], lambda c: handler)[0]
                return {}

            # Get schemas with caching
            schemas = []
            for cmd in commands:
                schema = get_cached_schema(cmd, lambda c=cmd: extract_schema(c))
                if schema:
                    schemas.append(schema)

            # DISCOVERY FIRST: Ensure skill.discover is first
            discover_schema = next((s for s in schemas if s.get("name") == "skill.discover"), None)
            if discover_schema:
                schemas = [discover_schema] + [
                    s for s in schemas if s.get("name") != "skill.discover"
                ]

            return schemas

        # Fallback: no kernel available, return empty list
        return []

    async def _execute_tool_call(self, tool_name: str, args: dict[str, Any]) -> str:
        """Execute a single tool call via kernel."""
        if self.kernel and hasattr(self.kernel, "execute_tool"):
            return await self.kernel.execute_tool(
                tool_name=tool_name,
                args=args,
                caller=None,  # OmniLoop has root privileges
            )

        # Direct execution via run_command - requires SkillContext initialization
        from omni.core.skills.runtime import run_command, get_skill_context
        from omni.foundation.config.skills import SKILLS_DIR

        # Ensure SkillContext is initialized
        get_skill_context(SKILLS_DIR())

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

        # Apply max_steps override if provided
        if max_steps is not None:
            self.config.max_tool_calls = max_steps

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
