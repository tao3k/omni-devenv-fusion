"""
planner.py - Task Decomposition Engine

Breaks down complex goals into parallelizable task graphs using:
- Cerebellum (sys_query) for dependency analysis
- Pattern matching for task type detection
- DAG construction for parallel execution

Integration: CortexOrchestrator → TaskDecomposer → TaskGraph
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

from omni.foundation.config.logging import get_logger

from .nodes import TaskGraph, TaskGroup, TaskNode, TaskPriority

logger = get_logger("omni.cortex.planner")


@dataclass
class DecompositionResult:
    """Result of task decomposition."""

    success: bool
    task_graph: TaskGraph | None
    analysis: dict[str, Any] | None
    error: str | None = None


@dataclass
class FileAnalysis:
    """Analysis of a file for task planning."""

    path: str
    functions: list[dict[str, Any]] = field(default_factory=list)
    classes: list[dict[str, Any]] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


class TaskDecomposer:
    """
    Advanced task decomposition engine.

    Responsibilities:
    1. Analyze high-level goals
    2. Use Cerebellum (sys_query) to scan affected code
    3. Build dependency graph (DAG)
    4. Generate parallelizable task groups

    Example:
        Goal: "Refactor all API endpoints"
        Analysis: Finds 5 controller files with 20 handler functions
        Output: 5 parallel task groups (one per file), each with sequential handlers
    """

    def __init__(self):
        self._analysis_cache: dict[str, FileAnalysis] = {}

    async def decompose(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> DecompositionResult:
        """
        Decompose a high-level goal into a task graph.

        Args:
            goal: The goal description to decompose
            context: Execution context (working_dir, scope, etc.)

        Returns:
            DecompositionResult with TaskGraph and analysis
        """
        try:
            logger.info("cortex.decomposition_started", goal=goal[:100])

            # Step 1: Analyze the goal type
            goal_type = self._classify_goal(goal)
            logger.info("cortex.goal_classified", goal=goal[:50], type=goal_type)

            # Step 2: Analyze affected scope using Cerebellum
            scope_analysis = await self._analyze_scope(goal, goal_type, context)
            logger.info("cortex.scope_analyzed", affected_files=len(scope_analysis))

            # Step 3: Build task graph based on goal type
            task_graph = await self._build_task_graph(goal, goal_type, scope_analysis, context)

            # Step 4: Validate graph
            if task_graph.detect_cycles():
                raise ValueError("Task graph contains cycles")

            logger.info(
                "cortex.decomposition_complete",
                tasks=len(task_graph.all_tasks),
                groups=len(task_graph.groups),
            )

            return DecompositionResult(
                success=True,
                task_graph=task_graph,
                analysis={
                    "goal": goal,
                    "goal_type": goal_type,
                    "scope_analysis": {
                        "files": len(scope_analysis),
                        "functions": sum(len(f.functions) for f in scope_analysis.values()),
                        "classes": sum(len(f.classes) for f in scope_analysis.values()),
                    },
                    "graph_summary": task_graph.summary(),
                },
            )

        except Exception as e:
            logger.error("cortex.decomposition_failed", error=str(e))
            return DecompositionResult(
                success=False,
                task_graph=None,
                analysis=None,
                error=str(e),
            )

    def _classify_goal(self, goal: str) -> str:
        """Classify the type of goal for appropriate decomposition strategy."""
        goal_lower = goal.lower()

        # Refactoring patterns
        if any(p in goal_lower for p in ["refactor", "rename", "move", "extract"]):
            return "refactor"

        # Testing patterns
        if any(p in goal_lower for p in ["test", "verify", "check"]):
            return "testing"

        # Documentation patterns
        if any(p in goal_lower for p in ["document", "docs", "readme"]):
            return "documentation"

        # Code generation patterns
        if any(p in goal_lower for p in ["add", "create", "implement", "generate"]):
            return "generation"

        # Search and analysis patterns
        if any(p in goal_lower for p in ["find", "search", "analyze", "audit"]):
            return "analysis"

        # Migration patterns
        if any(p in goal_lower for p in ["migrate", "convert", "upgrade", "port"]):
            return "migration"

        return "general"

    async def _analyze_scope(
        self,
        goal: str,
        goal_type: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, FileAnalysis]:
        """Analyze the scope of affected code using Cerebellum."""
        scope: dict[str, FileAnalysis] = {}

        # Extract potential file patterns from goal
        file_patterns = self._extract_file_patterns(goal)

        if not file_patterns:
            # Default: analyze current directory
            file_patterns = ["*.py"]

        # Use Cerebellum (sys_query) to scan for affected code elements
        try:
            from omni.core.skills.runtime.omni_cell import sys_query

            working_dir = context.get("working_dir", ".") if context else "."

            # Find Python files with relevant patterns
            for pattern in file_patterns:
                # Search for functions/classes matching the goal
                if goal_type in ["refactor", "generation"]:
                    # Look for function/class definitions
                    result = await sys_query(
                        {
                            "path": working_dir,
                            "pattern": "def $NAME",
                            "language": "python",
                            "captures": ["NAME"],
                        }
                    )

                    if result.success:
                        for item in result.items:
                            file_path = self._estimate_file_path(item, working_dir)
                            if file_path and file_path not in scope:
                                scope[file_path] = FileAnalysis(
                                    path=file_path,
                                    functions=[
                                        {
                                            "name": item["captures"].get("NAME"),
                                            "line": item["line_start"],
                                        }
                                    ],
                                )

        except Exception as e:
            logger.warning("cortex.scope_analysis_partial", error=str(e))

        return scope

    def _extract_file_patterns(self, goal: str) -> list[str]:
        """Extract file patterns from goal description."""
        patterns = []

        # Look for quoted strings (file paths)
        quoted = re.findall(r'["\']([^"\']+\.py)["\']', goal)
        patterns.extend(quoted)

        # Look for glob patterns
        globs = re.findall(r"\*\.py|\*\*/\*\.py|[a-zA-Z_]+\.py", goal)
        patterns.extend(globs)

        # Look for directory mentions
        dirs = re.findall(r"(?:src/|lib/|tests?|docs/)[^\s]*", goal)
        patterns.extend(dirs)

        return list(set(patterns)) if patterns else ["*.py"]

    def _estimate_file_path(self, item: dict, base: str) -> str | None:
        """Estimate file path from sys_query result."""
        # sys_query returns matched text with line info
        # In a full implementation, we'd map this back to the source file
        # For now, return a placeholder
        return item.get("metadata", {}).get("file") or None

    async def _build_task_graph(
        self,
        goal: str,
        goal_type: str,
        scope_analysis: dict[str, FileAnalysis],
        context: dict[str, Any] | None = None,
    ) -> TaskGraph:
        """Build the task graph based on goal type and scope."""
        task_graph = TaskGraph(name=f"graph_{goal[:30].replace(' ', '_')}")

        # Strategy based on goal type
        if goal_type == "refactor":
            return await self._build_refactor_graph(goal, scope_analysis, task_graph, context)
        elif goal_type == "testing":
            return await self._build_testing_graph(goal, scope_analysis, task_graph, context)
        elif goal_type == "generation":
            return await self._build_generation_graph(goal, scope_analysis, task_graph, context)
        else:
            return await self._build_general_graph(goal, scope_analysis, task_graph, context)

    async def _build_refactor_graph(
        self,
        goal: str,
        scope: dict[str, FileAnalysis],
        graph: TaskGraph,
        context: dict[str, Any] | None = None,
    ) -> TaskGraph:
        """Build task graph for refactoring operations."""
        # Extract refactor details
        old_name = self._extract_pattern(goal, r"(?:rename|refactor)\s+(?:\w+\s+)?(\w+)")
        new_name = self._extract_pattern(goal, r"(?:to|as|into)\s+(\w+)")

        # Create a group per file (can run in parallel)
        file_group = TaskGroup(
            id="refactor_files",
            name="File-level refactoring",
            execute_in_parallel=True,
            max_concurrent=5,
        )

        for file_path, analysis in scope.items():
            # Create sequential tasks for each refactoring step
            task = TaskNode(
                description=f"Refactor {file_path}",
                command=self._generate_refactor_command(goal, file_path, old_name, new_name),
                priority=TaskPriority.MEDIUM,
                metadata={
                    "file": file_path,
                    "goal_type": "refactor",
                    "old_name": old_name,
                    "new_name": new_name,
                },
            )
            file_group.add_task(task)

        graph.add_group(file_group)
        return graph

    async def _build_testing_graph(
        self,
        goal: str,
        scope: dict[str, FileAnalysis],
        graph: TaskGraph,
        context: dict[str, Any] | None = None,
    ) -> TaskGraph:
        """Build task graph for testing operations."""
        # Create parallel test groups
        test_group = TaskGroup(
            id="test_runs",
            name="Parallel test execution",
            execute_in_parallel=True,
            max_concurrent=3,
        )

        for file_path in scope.keys():
            task = TaskNode(
                description=f"Test {file_path}",
                command=f"python -m pytest {file_path} -v",
                priority=TaskPriority.HIGH,
                metadata={"file": file_path, "goal_type": "testing"},
            )
            test_group.add_task(task)

        graph.add_group(test_group)
        return graph

    async def _build_generation_graph(
        self,
        goal: str,
        scope: dict[str, FileAnalysis],
        graph: TaskGraph,
        context: dict[str, Any] | None = None,
    ) -> TaskGraph:
        """Build task graph for code generation."""
        # Sequential generation with dependencies
        generation_group = TaskGroup(
            id="code_generation",
            name="Sequential code generation",
            execute_in_parallel=False,
        )

        # Analyze generation steps
        steps = self._plan_generation_steps(goal)

        for i, step in enumerate(steps):
            task = TaskNode(
                description=step["description"],
                command=step["command"],
                priority=TaskPriority.CRITICAL if i == 0 else TaskPriority.MEDIUM,
                metadata={"step": i, "goal_type": "generation"},
            )
            if i > 0:
                # Previous steps are dependencies
                task.dependencies = [f"gen_step_{j}" for j in range(i)]

            task.id = f"gen_step_{i}"
            generation_group.add_task(task)

        graph.add_group(generation_group)
        return graph

    async def _build_general_graph(
        self,
        goal: str,
        scope: dict[str, FileAnalysis],
        graph: TaskGraph,
        context: dict[str, Any] | None = None,
    ) -> TaskGraph:
        """Build task graph for general operations."""
        # Create a simple task for the goal
        general_group = TaskGroup(
            id="general_tasks",
            name="General tasks",
            execute_in_parallel=False,
        )

        task = TaskNode(
            description=goal,
            command=goal,  # Execute the goal as a command
            priority=TaskPriority.MEDIUM,
            metadata={"goal_type": "general", "original_goal": goal},
        )
        general_group.add_task(task)

        graph.add_group(general_group)
        return graph

    def _generate_refactor_command(
        self,
        goal: str,
        file_path: str,
        old_name: str | None,
        new_name: str | None,
    ) -> str:
        """Generate the appropriate refactor command."""
        if old_name and new_name:
            return f"sed -i 's/\\b{old_name}\\b/{new_name}/g' {file_path}"
        return f"# Refactor: {goal} in {file_path}"

    def _extract_pattern(self, text: str, pattern: str) -> str | None:
        """Extract a regex pattern from text."""
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1) if match else None

    def _plan_generation_steps(self, goal: str) -> list[dict]:
        """Plan generation steps."""
        # Default generation steps
        return [
            {"description": "Analyze requirements", "command": f"# Analyze: {goal}"},
            {"description": "Generate code", "command": f"# Generate: {goal}"},
            {"description": "Verify output", "command": f"# Verify: {goal}"},
        ]


__all__ = [
    "TaskDecomposer",
    "DecompositionResult",
    "FileAnalysis",
]
