"""
universal_solver.py - OmniCell Integration Bridge

Binds Core execution layer to Evolution system via Tracer.
Enables trace recording of OmniCell successful executions for skill crystallization.

Integration: OmniCell → UniversalSolver → Tracer → Harvester → Factory → Immune → Skills
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.evolution.solver")


class SolverStatus(str, Enum):
    """Solver execution status."""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


@dataclass
class SolverResult:
    """Result from UniversalSolver execution."""

    task: str
    status: SolverStatus
    solution: str | None
    commands: list[str]
    outputs: list[str]
    duration_ms: float
    trace_id: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class UniversalSolver:
    """
    Integration bridge between Core OmniCell and Evolution system.

    Responsibilities:
    - Execute tasks via OmniCell
    - Record successful executions to TraceCollector
    - Recall experiences from Hippocampus for guided execution
    - Provide structured results for Harvester processing

    Integration with Hippocampus:
    - Recall similar experiences before task execution
    - Inject successful patterns into execution context

    Design: Imports OmniCell from Core at method level to avoid circular imports.
    """

    def __init__(
        self,
        trace_collector: "TraceCollector | None" = None,
        hippocampus=None,
    ):
        """Initialize the universal solver.

        Args:
            trace_collector: Optional TraceCollector instance. If not provided,
                           a default one will be created on first use.
            hippocampus: Optional Hippocampus instance for experience memory.
        """
        self._trace_collector = trace_collector
        self._omni_cell: "OmniCellRunner | None" = None
        self._hippocampus = hippocampus

    async def _get_trace_collector(self) -> "TraceCollector":
        """Lazy load TraceCollector if not provided."""
        if self._trace_collector is None:
            from omni.agent.core.evolution.tracer import TraceCollector

            self._trace_collector = TraceCollector()
        return self._trace_collector

    async def _get_omni_cell(self) -> "OmniCellRunner":
        """Lazy load OmniCellRunner from Core."""
        if self._omni_cell is None:
            # Import from Core to avoid circular dependency at module level
            from omni.core.skills.runtime.omni_cell import OmniCellRunner

            self._omni_cell = OmniCellRunner()
        return self._omni_cell

    async def _get_hippocampus(self):
        """Lazy load Hippocampus for experience memory."""
        if self._hippocampus is None:
            from omni.agent.core.memory.hippocampus import get_hippocampus

            self._hippocampus = get_hippocampus()
        return self._hippocampus

    def _format_experiences_for_context(self, experiences: list) -> str:
        """Format recalled experiences for injection into execution context.

        Args:
            experiences: List of ExperienceRecallResult from Hippocampus

        Returns:
            Formatted string describing past successful approaches
        """
        if not experiences:
            return ""

        formatted_parts = ["# Past Successful Experiences:\n"]

        for i, exp in enumerate(experiences[:3], 1):
            formatted_parts.append(f"## Experience {i} (similarity: {exp.similarity_score:.2f})")
            formatted_parts.append(f"Task: {exp.task_description}")
            if exp.nu_pattern:
                formatted_parts.append(f"Pattern: {exp.nu_pattern}")
            if exp.steps:
                commands = [s.command for s in exp.steps if s.success]
                formatted_parts.append(f"Commands: {' → '.join(commands)}")
            formatted_parts.append("")

        return "\n".join(formatted_parts)

    async def solve(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        record_trace: bool = True,
    ) -> SolverResult:
        """Execute task via OmniCell and optionally record trace.

        Args:
            task: Task description to execute
            context: Optional execution context (working_dir, env, etc.)
            record_trace: Whether to record successful execution to Tracer

        Returns:
            SolverResult with execution details and optional trace_id
        """
        start_time = datetime.now()
        commands: list[str] = []
        outputs: list[str] = []
        status = SolverStatus.SUCCESS
        error: str | None = None
        trace_id: str | None = None

        try:
            omni_cell = await self._get_omni_cell()

            # [HIPPOCAMPS] Recall relevant experiences before planning
            experience_context = ""
            try:
                hippocampus = await self._get_hippocampus()
                experiences = await hippocampus.recall_experience(
                    query=task,
                    limit=3,
                )
                if experiences:
                    experience_context = self._format_experiences_for_context(experiences)
                    logger.info(
                        "evolution.hippocampus_guiding_execution",
                        experience_count=len(experiences),
                        task=task[:50],
                    )
            except Exception as e:
                logger.debug("evolution.hippocampus_recall_skipped", error=str(e))

            # Determine execution strategy based on task
            execution_plan = await self._plan_execution(task, context, experience_context)

            # Execute commands
            for cmd in execution_plan:
                commands.append(cmd)
                try:
                    output = await omni_cell.execute(cmd)
                    outputs.append(output)
                except Exception as e:
                    outputs.append(f"Error: {e}")
                    status = SolverStatus.FAILED
                    error = str(e)
                    break

            # Record successful execution to Tracer
            if record_trace and status == SolverStatus.SUCCESS:
                tracer = await self._get_trace_collector()
                trace_id = await tracer.record(
                    task_id=self._generate_task_id(task),
                    task_description=task,
                    commands=commands,
                    outputs=outputs,
                    success=True,
                    duration_ms=self._calculate_duration(start_time),
                    metadata=context or {},
                )
                logger.info(
                    "evolution.trace_recorded",
                    task=task,
                    command_count=len(commands),
                    trace_id=trace_id,
                )

        except Exception as e:
            status = SolverStatus.FAILED
            error = f"Execution failed: {e}"
            logger.error("evolution.solver_error", task=task, error=error)

        duration = self._calculate_duration(start_time)

        return SolverResult(
            task=task,
            status=status,
            solution=outputs[-1] if outputs else None,
            commands=commands,
            outputs=outputs,
            duration_ms=duration,
            trace_id=trace_id,
            error=error,
        )

    async def _plan_execution(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        experience_context: str = "",
    ) -> list[str]:
        """Generate execution plan from task description.

        Args:
            task: Task description
            context: Execution context
            experience_context: Optional context from similar past experiences

        Returns:
            List of commands to execute
        """
        # If we have experience context, try to use it for better planning
        if experience_context:
            logger.debug(
                "evolution.using_experience_context", context_preview=experience_context[:100]
            )
        # Simple task-to-command mapping for common patterns
        # In production, this would use LLM for complex tasks

        task_lower = task.lower()

        if "list" in task_lower and "file" in task_lower:
            return ["ls -la"]
        elif "find" in task_lower and "file" in task_lower:
            # Extract search pattern
            pattern = self._extract_pattern(task)
            return [f"find . -name '{pattern}' -type f"]
        elif "git status" in task_lower:
            return ["git status"]
        elif "git commit" in task_lower:
            # Extract commit message
            message = self._extract_commit_message(task)
            return ["git add -A", f'git commit -m "{message}"']
        elif "python test" in task_lower or "pytest" in task_lower:
            return ["python -m pytest -v"]
        else:
            # Default: treat as shell command
            return [task]

    def _extract_pattern(self, task: str) -> str:
        """Extract file pattern from task description."""
        import re

        # Look for patterns like "*.py", "test_*.py", etc.
        match = re.search(r"\*\.?\w+", task)
        if match:
            return match.group(0)
        return "*"

    def _extract_commit_message(self, task: str) -> str:
        """Extract commit message from task description."""
        # Look for quoted message or descriptive text
        import re

        # Look for patterns like "commit: message" or "git commit: message"
        match = re.search(r"(?:commit[:\s]+)(.+?)(?:\s*$|\s+for\s+)", task, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Use task description as message
        return task.strip()[:50]

    def _generate_task_id(self, task: str) -> str:
        """Generate a task ID from task description."""
        import hashlib

        # Create short hash from task + timestamp
        content = f"{task}_{datetime.now().isoformat()}"
        short_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"task_{short_hash}"

    def _calculate_duration(self, start: datetime) -> float:
        """Calculate execution duration in milliseconds."""
        from datetime import timedelta

        delta = datetime.now() - start
        return delta.total_seconds() * 1000

    async def record_failure(
        self,
        task: str,
        commands: list[str],
        outputs: list[str],
        error: str,
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """Record a failed execution attempt for learning.

        Args:
            task: Task description
            commands: Commands that were attempted
            outputs: Outputs from commands
            error: Error message
            context: Execution context

        Returns:
            Trace ID if recording succeeded, None otherwise
        """
        tracer = await self._get_trace_collector()
        trace_id = await tracer.record(
            task_id=self._generate_task_id(task),
            task_description=task,
            commands=commands,
            outputs=outputs + [f"Error: {error}"],
            success=False,
            duration_ms=0,
            metadata={
                **(context or {}),
                "error_type": "execution_failure",
                "error_message": error,
            },
        )
        return trace_id

    async def get_execution_history(
        self, task_pattern: str | None = None, limit: int = 50
    ) -> list[SolverResult]:
        """Get execution history from Tracer.

        Args:
            task_pattern: Optional pattern to filter traces
            limit: Maximum number of traces to return

        Returns:
            List of SolverResult objects
        """
        tracer = await self._get_trace_collector()

        if task_pattern:
            traces = await tracer.get_traces_by_task(task_pattern)
        else:
            traces = await tracer.get_recent_traces(limit)

        return [
            SolverResult(
                task=t.task_description,
                status=SolverStatus.SUCCESS if t.success else SolverStatus.FAILED,
                solution=t.outputs[-1] if t.outputs else None,
                commands=t.commands,
                outputs=t.outputs,
                duration_ms=t.duration_ms,
                trace_id="",  # TraceCollector returns IDs, not stored here
            )
            for t in traces
        ]


# Type hints for forward references
from omni.agent.core.evolution.tracer import TraceCollector

__all__ = [
    "UniversalSolver",
    "SolverResult",
    "SolverStatus",
]
