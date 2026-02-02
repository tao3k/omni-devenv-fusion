"""
orchestrator.py - Prefrontal Cortex Parallel Execution Engine

Orchestrates concurrent task execution with:
- Dependency-aware scheduling
- Parallel group execution
- Result aggregation and conflict detection
- Cost-aware reflection
- TUI Integration

Integration: TaskDecomposer → CortexOrchestrator → UniversalSolver → OmniCell
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Protocol

from omni.foundation.config.logging import get_logger

from .nodes import TaskGraph, TaskGroup, TaskNode, TaskStatus, TaskPriority
from .planner import TaskDecomposer, DecompositionResult

logger = get_logger("omni.cortex.orchestrator")


class TUIBridgeProtocol(Protocol):
    """Protocol for TUI event emission."""

    @property
    def is_active(self) -> bool: ...

    async def send_event(self, topic: str, payload: dict[str, Any]) -> None: ...


@dataclass
class ExecutionConfig:
    """Configuration for parallel execution."""

    max_concurrent_groups: int = 5
    max_concurrent_tasks: int = 10
    default_timeout_seconds: int = 300
    retry_failed_tasks: bool = True
    stop_on_failure: bool = False
    collect_metrics: bool = True


@dataclass
class ExecutionResult:
    """Result of a complete execution."""

    success: bool
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    duration_ms: float = 0
    results: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_tasks == 0:
            return 0.0
        return self.completed_tasks / self.total_tasks


class CortexOrchestrator:
    """
    Parallel task orchestration engine with TUI support.

    Responsibilities:
    1. Receive decomposed task graphs
    2. Execute task groups in parallel (dependency-aware)
    3. Collect and aggregate results
    4. Detect and handle conflicts
    5. Provide execution metrics
    6. Emit events to TUI for visualization

    Example:
        orchestrator = CortexOrchestrator(tui_bridge=tui)
        result = await orchestrator.execute(task_graph)
    """

    def __init__(
        self,
        config: ExecutionConfig | None = None,
        tui_bridge: Optional[TUIBridgeProtocol] = None,
    ):
        self.config = config or ExecutionConfig()
        self.decomposer = TaskDecomposer()
        self.tui = tui_bridge
        self._semaphore: asyncio.Semaphore | None = None
        self._execution_id: str | None = None
        self._start_time: datetime | None = None

    async def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        """Emit event to TUI if active."""
        if self.tui and self.tui.is_active:
            try:
                await self.tui.send_event(topic, payload)
            except Exception as e:
                logger.debug(f"Failed to emit TUI event: {e}")

    async def execute(
        self,
        task_graph: TaskGraph,
        context: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """
        Execute a task graph with parallel execution.

        Args:
            task_graph: The task graph to execute
            context: Execution context

        Returns:
            ExecutionResult with all task outcomes
        """
        self._execution_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._start_time = datetime.now()

        logger.info(
            "cortex.execution_started",
            execution_id=self._execution_id,
            tasks=len(task_graph.all_tasks),
            groups=len(task_graph.groups),
        )

        # Emit TUI event for execution start
        await self._emit(
            "cortex/start",
            {
                "execution_id": self._execution_id,
                "total_tasks": len(task_graph.all_tasks),
                "groups": len(task_graph.groups),
            },
        )

        # Initialize concurrency control
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_tasks)

        completed_tasks: set[str] = set()
        results: dict[str, Any] = {}
        errors: list[str] = []

        try:
            # Get execution order
            group_order = task_graph.get_group_execution_order()

            for group_id in group_order:
                group = task_graph.groups.get(group_id)
                if not group:
                    continue

                logger.info(
                    "cortex.executing_group",
                    group_id=group_id,
                    group_name=group.name,
                    task_count=len(group.tasks),
                )

                # Emit TUI event for group start
                await self._emit(
                    "cortex/group/start",
                    {
                        "group_id": group.id,
                        "name": group.name,
                        "parallel": group.execute_in_parallel,
                        "task_count": len(group.tasks),
                    },
                )

                # Execute group (parallel or sequential)
                group_results = await self._execute_group(
                    group, task_graph, completed_tasks, context
                )

                # Collect results
                results[group_id] = group_results

                # Count completed and failed
                group_completed = 0
                group_failed = 0

                # Update completed tasks
                for task_id, result in group_results.items():
                    if result["status"] == "success":
                        completed_tasks.add(task_id)
                        results[task_id] = result
                        group_completed += 1
                    else:
                        errors.append(f"{task_id}: {result.get('error', 'Unknown error')}")
                        group_failed += 1

                        if self.config.stop_on_failure:
                            logger.warning("cortex.stopping_on_failure", task=task_id)
                            await self._emit(
                                "cortex/error",
                                {
                                    "task_id": task_id,
                                    "error": result.get("error", "Unknown error"),
                                },
                            )
                            return ExecutionResult(
                                success=False,
                                total_tasks=len(task_graph.all_tasks),
                                completed_tasks=len(completed_tasks),
                                failed_tasks=len(errors),
                                results=results,
                                errors=errors,
                            )

                # Emit TUI event for group completion
                await self._emit(
                    "cortex/group/complete",
                    {
                        "group_id": group.id,
                        "name": group.name,
                        "completed": group_completed,
                        "failed": group_failed,
                    },
                )

            # Calculate final metrics
            duration_ms = (datetime.now() - self._start_time).total_seconds() * 1000

            success = len(errors) == 0

            logger.info(
                "cortex.execution_complete",
                execution_id=self._execution_id,
                success=success,
                completed=len(completed_tasks),
                failed=len(errors),
                duration_ms=duration_ms,
            )

            # Emit TUI event for execution complete
            await self._emit(
                "cortex/complete",
                {
                    "execution_id": self._execution_id,
                    "success": success,
                    "completed": len(completed_tasks),
                    "failed": len(errors),
                    "duration_ms": duration_ms,
                },
            )

            return ExecutionResult(
                success=success,
                total_tasks=len(task_graph.all_tasks),
                completed_tasks=len(completed_tasks),
                failed_tasks=len(errors),
                duration_ms=duration_ms,
                results=results,
                errors=errors,
                metrics=self._collect_metrics(task_graph, completed_tasks, duration_ms),
            )

        except Exception as e:
            logger.error("cortex.execution_error", error=str(e))
            return ExecutionResult(
                success=False,
                total_tasks=len(task_graph.all_tasks),
                completed_tasks=len(completed_tasks),
                failed_tasks=len(completed_tasks),
                errors=[str(e)],
            )

    async def execute_from_goal(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """
        Decompose a goal and execute the resulting task graph.

        Args:
            goal: The goal description
            context: Execution context

        Returns:
            ExecutionResult from task execution
        """
        # Step 1: Decompose the goal
        decomposition = await self.decomposer.decompose(goal, context)

        if not decomposition.success:
            return ExecutionResult(
                success=False,
                errors=[decomposition.error or "Decomposition failed"],
            )

        # Step 2: Execute the task graph
        return await self.execute(decomposition.task_graph, context)

    async def _execute_group(
        self,
        group: TaskGroup,
        task_graph: TaskGraph,
        completed_tasks: set[str],
        context: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Execute a task group."""
        results: dict[str, dict[str, Any]] = {}

        if group.execute_in_parallel:
            # Parallel execution within group
            tasks_to_run = group.get_ready_tasks(completed_tasks)

            logger.info(
                "cortex.parallel_group",
                group_id=group.id,
                task_count=len(tasks_to_run),
            )

            # Create coroutines for each task
            coroutines = [
                self._execute_task(task, completed_tasks, context) for task in tasks_to_run
            ]

            # Execute with concurrency limit
            async def limited_gather():
                results_list = []
                for coro in asyncio.as_completed(coroutines):
                    async with self._semaphore:
                        result = await coro
                        results_list.append(result)
                return results_list

            group_results = await limited_gather()
            for task_id, result in group_results:
                results[task_id] = result

        else:
            # Sequential execution within group
            ready_tasks = group.get_ready_tasks(completed_tasks)

            logger.info(
                "cortex.sequential_group",
                group_id=group.id,
                task_count=len(ready_tasks),
            )

            for task in ready_tasks:
                task_id, result = await self._execute_task(task, completed_tasks, context)
                results[task_id] = result

        return results

    async def _execute_task(
        self,
        task: TaskNode,
        completed_tasks: set[str],
        context: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Execute a single task via UniversalSolver."""
        task.started_at = datetime.now()
        task.status = TaskStatus.RUNNING

        logger.info(
            "cortex.executing_task",
            task_id=task.id,
            description=task.description[:50],
        )

        # Emit TUI event for task start
        await self._emit(
            "task/start",
            {
                "task_id": task.id,
                "description": task.description,
                "command": task.command,
            },
        )

        try:
            # Execute via UniversalSolver
            result = await self._run_with_solver(task.command, context)

            task.status = TaskStatus.SUCCESS
            task.result = result
            task.completed_at = datetime.now()

            logger.info(
                "cortex.task_success",
                task_id=task.id,
                duration_ms=task.duration_ms,
            )

            # Emit TUI event for task success
            await self._emit(
                "task/complete",
                {
                    "task_id": task.id,
                    "status": "success",
                    "duration_ms": task.duration_ms,
                    "output_preview": str(result)[:100] if result else "",
                },
            )

            return task.id, {
                "status": "success",
                "command": task.command,
                "result": result,
                "duration_ms": task.duration_ms,
                "metadata": task.metadata,
            }

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()

            # Retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                logger.info(
                    "cortex.task_retry",
                    task_id=task.id,
                    attempt=task.retry_count,
                )

                # Emit TUI event for retry
                await self._emit(
                    "task/retry",
                    {
                        "task_id": task.id,
                        "attempt": task.retry_count,
                        "error": str(e),
                    },
                )

                return await self._execute_task(task, completed_tasks, context)

            logger.error(
                "cortex.task_failed",
                task_id=task.id,
                error=str(e),
            )

            # Emit TUI event for task failure
            await self._emit(
                "task/fail",
                {
                    "task_id": task.id,
                    "error": str(e),
                    "retry_count": task.retry_count,
                },
            )

            return task.id, {
                "status": "failed",
                "command": task.command,
                "error": str(e),
                "duration_ms": task.duration_ms,
                "metadata": task.metadata,
                "retry_count": task.retry_count,
            }

    async def _run_with_solver(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute command via UniversalSolver."""
        try:
            from omni.agent.core.evolution.universal_solver import UniversalSolver

            solver = UniversalSolver()
            result = await solver.solve(
                task=command,
                context=context or {},
                record_trace=False,
            )

            return {
                "output": result.solution,
                "commands": result.commands,
                "status": result.status.value,
            }

        except ImportError:
            # Fallback: Direct OmniCell execution
            from omni.core.skills.runtime.omni_cell import OmniCellRunner

            omni_cell = OmniCellRunner()
            cell_result = await omni_cell.run(command)

            return {
                "output": cell_result.data,
                "status": cell_result.status,
            }

    def _collect_metrics(
        self,
        task_graph: TaskGraph,
        completed_tasks: set[str],
        duration_ms: float,
    ) -> dict[str, Any]:
        """Collect execution metrics."""
        return {
            "execution_id": self._execution_id,
            "total_tasks": len(task_graph.all_tasks),
            "completed_tasks": len(completed_tasks),
            "total_groups": len(task_graph.groups),
            "execution_levels": len(task_graph.get_execution_levels()),
            "duration_ms": duration_ms,
            "throughput_tasks_per_sec": len(completed_tasks) / (duration_ms / 1000)
            if duration_ms > 0
            else 0,
            "config": {
                "max_concurrent": self.config.max_concurrent_tasks,
                "retry_enabled": self.config.retry_failed_tasks,
            },
        }


class ConflictDetector:
    """
    Detect and resolve conflicts between concurrent modifications.

    Responsibilities:
    - Track file modifications across tasks
    - Detect overlapping changes
    - Suggest resolution strategies
    """

    def __init__(self):
        self._modified_files: dict[str, set[str]] = {}  # file -> {task_ids}

    def register_modification(self, task_id: str, file_path: str) -> None:
        """Register that a task modified a file."""
        if file_path not in self._modified_files:
            self._modified_files[file_path] = set()
        self._modified_files[file_path].add(task_id)

    def detect_conflicts(self, modifications: list[dict]) -> list[dict]:
        """Detect conflicts in a list of modifications."""
        conflicts = []
        file_tasks: dict[str, list[dict]] = {}

        for mod in modifications:
            file_path = mod.get("file")
            if file_path:
                if file_path not in file_tasks:
                    file_tasks[file_path] = []
                file_tasks[file_path].append(mod)

        # Check for overlapping modifications
        for file_path, mods in file_tasks.items():
            if len(mods) > 1:
                # Multiple tasks modified the same file
                conflict = {
                    "type": "file_conflict",
                    "file": file_path,
                    "conflicting_tasks": [m.get("task_id") for m in mods],
                    "suggestion": "Merge changes or execute sequentially",
                }
                conflicts.append(conflict)

        return conflicts

    def get_modified_files(self) -> dict[str, set[str]]:
        """Get all modified files and their modifying tasks."""
        return self._modified_files.copy()


__all__ = [
    "CortexOrchestrator",
    "ExecutionConfig",
    "ExecutionResult",
    "ConflictDetector",
]
