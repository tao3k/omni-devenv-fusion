"""
loop.py - OmniLoop Orchestrator
Feature: Adaptive Skill Projection & Cognitive Constraints

MatureReAct Loop implementation with smart context management.
Integrates ResilientReAct workflow with ContextManager for conversation handling.

Key Features:
- Adaptive Skill Projection: Hides atomic tools when high-level skills exist.
- Resilient Execution: Uses ResilientReAct for robust tool handling.
- Harvester Integration: Background learning from successful sessions.

Usage:
    from omni.agent.core.omni import OmniLoop, OmniLoopConfig

    loop = OmniLoop(kernel=kernel)
    result = await loop.run("Your task here")
"""

import asyncio
import json
import re
import time
import uuid
from typing import Any, List, Dict, Optional

from omni.agent.core.context.manager import ContextManager
from omni.agent.core.context.pruner import ContextPruner, PruningConfig
from omni.core.context.orchestrator import create_omni_loop_context
from omni.foundation.config.logging import get_logger
from omni.foundation.config.settings import get_setting
from omni.foundation.services.llm import InferenceClient

logger = get_logger("omni.agent.loop")

# Event-driven checkpoint saving (Step 4)
try:
    from omni_core_rs import PyGlobalEventBus

    EVENT_BUS_AVAILABLE = True
except ImportError:
    EVENT_BUS_AVAILABLE = False
    logger.warning("Rust Event Bus not available, checkpoint events disabled")

from .config import OmniLoopConfig
from .react import ResilientReAct
from .schemas import extract_tool_schemas
from ..memory.archiver import MemoryArchiver

logger = get_logger("omni.agent.loop")

# Tier 1: Atomic Tools (Low-level, Noise prone)
TIER_1_ATOMIC = {
    "filesystem.read_file",
    "filesystem.write_file",
    "filesystem.list_dir",
    "filesystem.delete_file",
    "terminal.run_command",
    "terminal.analyze_last_error",  # Often hallucinated
}

# High-level skill indicators
HIGH_LEVEL_KEYWORDS = ["researcher", "code_tools", "git_smart", "software_engineering"]

# Epistemic Gating - Ambiguity detection patterns
VAGUE_TASK_PATTERNS = [
    r"^do\s+(something|anything|stuff)$",
    r"^fix\s+(it|this|that|things?)$",
    r"^improve\s+(it|this|that|things?)$",
    r"^help\s+(me|us)$",
    r"^make\s+(it|this|that)\s+(work|better|goto)$",
    r"^goto\s*$",
    r"^go\s+there\s*$",
    r"^\w+\s+\w+\s*$",  # Very short two-word tasks
]

# Information seeking patterns
INFO_SEEKING_PATTERNS = [
    r"(what|which|who|where|when|why|how).*\?$",
    r"tell\s+me\s+about",
    r"explain\s+(me|how|what|why)",
    r"describe\s+",
]


class EpistemicGater:
    """Cognitive Gate - Verifies task intent before execution."""

    def __init__(self, min_task_length: int = 5):
        self.min_task_length = min_task_length
        self._compiled_patterns = [
            (re.compile(p, re.IGNORECASE), "vague") for p in VAGUE_TASK_PATTERNS
        ]
        self._compiled_info_patterns = [
            (re.compile(p, re.IGNORECASE), "info_seeking") for p in INFO_SEEKING_PATTERNS
        ]

    def evaluate(self, task: str) -> tuple[bool, str, dict[str, Any]]:
        """Evaluate if the task should proceed or needs clarification."""
        task = task.strip()
        metadata: dict[str, Any] = {}

        if not task or len(task) < self.min_task_length:
            return (
                False,
                "Task is too short or empty. Please provide more details.",
                {"suggestion": "Describe what you want to accomplish in more detail."},
            )

        for pattern, ptype in self._compiled_patterns:
            if pattern.match(task):
                return (
                    False,
                    f"Task '{task}' is too vague. Please be more specific.",
                    {"ambiguity_type": ptype},
                )

        for pattern, ptype in self._compiled_info_patterns:
            if pattern.search(task):
                return (True, "Information seeking task", {"task_type": "info_seeking"})

        if "file" in task.lower() and "path" not in task.lower():
            metadata["context_warning"] = "Task mentions 'file' but no path specified"

        return (True, "Task appears valid", metadata)


class OmniLoop:
    """
    Cognitive Loop Manager with Epistemic Gating.

    Key Features:
    - Adaptive Skill Projection: Hides atomic tools when high-level skills exist.
    - Resilient Execution: Uses ResilientReAct for robust tool handling.
    - Harvester Integration: Background learning from successful sessions.
    """

    def __init__(self, config: Optional[OmniLoopConfig] = None, kernel: Any = None):
        self.config = config or OmniLoopConfig()
        self.session_id = str(uuid.uuid4())[:8]
        self.kernel = kernel
        self.current_step = 0  # Track step for event publishing

        # Epistemic Gating
        self._epistemic_gater = EpistemicGater()

        # Initialize Context with Rust-powered pruner
        pruning_config = PruningConfig(
            max_tokens=self.config.max_tokens,
            retained_turns=self.config.retained_turns,
            max_tool_output=self.config.max_tool_output,
        )
        self.context = ContextManager(pruner=ContextPruner(config=pruning_config))

        self.engine = InferenceClient()
        self.orchestrator = create_omni_loop_context()
        self.history: List[Dict[str, Any]] = []
        self._initialized = False

        # [NEW] Initialize Memory Archiver for long-term storage
        self.archiver = MemoryArchiver()

    async def _ensure_initialized(self):
        if self._initialized:
            return

        # Build System Context with Protocol Constraints
        state = {"session_id": self.session_id}
        try:
            base_prompt = await self.orchestrator.build_context(state)

            # Cognitive Constraint Injection
            constraint_prompt = (
                "\n\n[COGNITIVE PROTOCOL]\n"
                "1. DO NOT act as a text editor. Use High-Level Skills (`researcher`, `code_tools`) first.\n"
                "2. `skill.discover` is MANDATORY for unknown capabilities.\n"
                "3. Stop immediately if you are stuck in a loop.\n"
                "4. Output 'EXIT_LOOP_NOW' only when the user's intent is fully satisfied."
            )
            self.context.add_system_message(base_prompt + constraint_prompt)
        except Exception as e:
            logger.error(f"Context build failed: {e}")
            self.context.add_system_message("You are Omni-Dev Fusion. Use high-level skills.")

        self._initialized = True

    def _publish_step_complete(self, state: Dict[str, Any]) -> None:
        """Fire-and-forget checkpoint event to Rust Event Bus (Step 4).

        Replaces blocking checkpoint.save() with async event publishing.
        The persistence service subscribes to 'agent/step_complete' and saves to LanceDB.
        """
        if not EVENT_BUS_AVAILABLE:
            return

        try:
            self.current_step += 1

            payload = json.dumps(
                {
                    "thread_id": self.session_id,
                    "step": self.current_step,
                    "state": state,
                    "timestamp": time.time(),
                }
            )

            # Non-blocking publish to Rust GLOBAL_BUS
            # "agent" is source, "agent/step_complete" is topic
            PyGlobalEventBus.publish("agent", "agent/step_complete", payload)
            logger.debug(f"📡 Published step_complete event (step {self.current_step})")

        except Exception as e:
            logger.warning(f"Failed to publish step event: {e}")

    async def _get_adaptive_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Implements Adaptive Skill Projection.
        Filters out 'Atomic' tools if 'Molecular' skills are available.
        """
        if not self.kernel:
            return []

        from omni.core.cache.tool_schema import get_cached_schema

        # 1. Get All Core Commands
        commands = self.kernel.skill_context.get_core_commands()

        # 2. Epistemic Gating Logic
        # Check if we have high-level skills loaded
        has_high_level = any(
            kw in cmd
            for c in commands
            for kw in HIGH_LEVEL_KEYWORDS
            for cmd in [c]
            if isinstance(c, str)
        )

        filtered_commands = []
        if self.config.suppress_atomic_tools and has_high_level:
            # Filter logic: Keep tool if NOT in atomic list OR if explicitly whitelisted
            filtered_commands = [c for c in commands if c not in TIER_1_ATOMIC]
            # Always ensure discovery is available
            if "skill.discover" not in filtered_commands and "skill.discover" in commands:
                filtered_commands.append("skill.discover")
        else:
            filtered_commands = commands

        # 3. Dynamic Limit Enforcement
        if len(filtered_commands) > self.config.max_tool_schemas:
            # Sort to prioritize discovery and high-level tools
            filtered_commands.sort(key=lambda x: (x != "skill.discover", x in TIER_1_ATOMIC))
            filtered_commands = filtered_commands[: self.config.max_tool_schemas]

        # 4. Extract Schemas using Cache
        schemas = []

        def extract_cb(c):
            handler = self.kernel.skill_context.get_command(c)
            if handler:
                result = extract_tool_schemas([c], lambda _: handler)
                return result[0] if result else {}
            return {}

        for cmd in filtered_commands:
            s = get_cached_schema(cmd, lambda c=cmd: extract_cb(c))
            if s:
                schemas.append(s)

        return schemas

    async def _execute_tool_proxy(self, name: str, args: Dict[str, Any]) -> Any:
        """Secure Proxy for Tool Execution."""
        if self.kernel:
            return await self.kernel.execute_tool(name, args, caller="OmniLoop")

        # Fallback for standalone testing
        from omni.core.skills.runtime import run_command, get_skill_context
        from omni.foundation.config.skills import SKILLS_DIR

        get_skill_context(SKILLS_DIR())
        return await run_command(name, **args)

    def _has_high_level_skill(self, tool_names: List[str]) -> bool:
        """Check if any high-level skill is present in tool names."""
        for tool_name in tool_names:
            for keyword in HIGH_LEVEL_KEYWORDS:
                if keyword in tool_name.lower():
                    return True
        return False

    def _filter_tier_1_atomic(self, tool_names: List[str]) -> List[str]:
        """Filter out TIER_1_ATOMIC tools from the list."""
        return [name for name in tool_names if name not in TIER_1_ATOMIC]

    async def run(self, task: str, max_steps: Optional[int] = None) -> str:
        """Execute a task through the MatureReAct loop."""
        # Epistemic Gating
        if self._epistemic_gater is not None:
            should_proceed, reason, metadata = self._epistemic_gater.evaluate(task)
            if not should_proceed:
                self.history.extend(
                    [
                        {"role": "user", "content": task},
                        {"role": "assistant", "content": reason},
                    ]
                )
                return reason

        await self._ensure_initialized()

        # Memory Recall (Fast Path - Associative)
        await self._inject_memory_context(task)

        # Configure limits
        steps_limit = max_steps if max_steps else self.config.max_tool_calls

        self.context.add_user_message(task)

        # Initialize Resilient Workflow
        workflow = ResilientReAct(
            engine=self.engine,
            get_tool_schemas=self._get_adaptive_tool_schemas,
            execute_tool=self._execute_tool_proxy,
            max_tool_calls=steps_limit,
            max_consecutive_errors=self.config.max_consecutive_errors,
            verbose=self.config.verbose,
        )

        # Execute
        response = await workflow.run(
            task=task,
            system_prompt=self.context.get_system_prompt(),
            messages=self.context.get_active_context(),
        )

        # Post-processing
        self.context.update_last_assistant(response)
        self.step_count = workflow.step_count
        self.tool_calls_count = workflow.tool_calls_count

        self.history.extend(
            [{"role": "user", "content": task}, {"role": "assistant", "content": response}]
        )

        # [NEW] Flush to Long-Term Memory (MemoryArchiver)
        # Archiver handles incremental sync - only stores new messages
        self.archiver.archive_turn(self.history)

        # [Step 4] Fire-and-forget checkpoint to Rust Event Bus
        # This replaces blocking checkpoint.save() with async event publishing
        self._publish_step_complete(
            {
                "session_id": self.session_id,
                "task": task,
                "response": response,
                "step_count": self.step_count,
                "tool_calls": self.tool_calls_count,
            }
        )

        # Fire-and-forget learning
        asyncio.create_task(self._trigger_harvester())

        return response

    async def _inject_memory_context(self, task: str) -> None:
        """
        Associative Recall

        Before acting, check if we have relevant memories/rules for this task.
        Fast Path (System 1) - Automatic rule/preference injection.
        """
        try:
            # Import here to avoid circular dependencies
            from omni.foundation.services.vector import get_vector_store

            store = get_vector_store()

            # Search for relevant memories (Top 3, threshold 0.75)
            memories = await store.search(query=task, n_results=3)

            if not memories:
                return

            # Format memories into context block
            memory_block = "\n[RECALLED MEMORIES - PREVIOUS LESSONS]\n"
            for m in memories:
                source = m.metadata.get("domain", "User")
                memory_block += f"- {m.content} (Source: {source})\n"
            memory_block += "[End of Memories]\n\n"

            # Inject into System Context
            self.context.add_system_message(memory_block)
            logger.info(f"🧠 Injected {len(memories)} memories into context")

        except ImportError:
            # VectorStore not available, skip silently
            logger.debug("VectorStore not available, skipping memory recall")
        except Exception as e:
            logger.warn(f"Memory recall failed: {e}")

    async def _trigger_harvester(self):
        """
        Background Protocol: Self-Evolution

        Dual-Path Evolution:
        - Slow Path: Harvest successful workflows as new skills
        - Fast Path: Extract rules/preferences to VectorStore
        """
        if not self.history:
            return

        try:
            # Lazy import to avoid startup dependencies
            from omni.agent.core.evolution.harvester import Harvester
            from omni.agent.core.evolution.factory import SkillFactory
            from omni.foundation.config.skills import SKILLS_DIR
            from omni.foundation.services.vector import get_vector_store

            harvester = Harvester(self.engine)

            # Slow Path: Harvest Procedural Skills
            candidate = await harvester.analyze_session(self.history)

            if candidate:
                output_dir = SKILLS_DIR() / "harvested"
                path = SkillFactory.synthesize(candidate, output_dir)
                logger.info(f"🧬 Evolved new skill: {path}")

            # Fast Path: Harvest Semantic Lessons
            lesson = await harvester.extract_lessons(self.history)

            if lesson:
                # Save to VectorStore
                store = get_vector_store()
                success = await store.add(
                    content=lesson.rule,
                    metadata={"domain": lesson.domain, "confidence": lesson.confidence},
                )
                if success:
                    logger.info(f"🧠 Learned rule: {lesson.rule} (domain: {lesson.domain})")

        except ImportError as e:
            logger.debug(f"Evolution dependencies not available: {e}")
        except Exception as e:
            logger.error(f"Evolution cycle failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        return {
            "session_id": self.session_id,
            "step_count": getattr(self, "step_count", 0),
            "tool_calls": getattr(self, "tool_calls_count", 0),
            "context_stats": self.context.stats(),
        }

    def snapshot(self) -> Dict[str, Any]:
        """Create a serializable snapshot of the current session."""
        return {
            "session_id": self.session_id,
            "step_count": getattr(self, "step_count", 0),
            "context": self.context.snapshot(),
            "history": self.history,
        }
