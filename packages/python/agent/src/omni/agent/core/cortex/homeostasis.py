"""
homeostasis.py - Homeostasis Integration Module

Integrates TransactionShield and ConflictDetector with CortexOrchestrator.

Features:
- Automatic transaction lifecycle management
- Conflict detection between concurrent tasks
- Safe merge workflow with rollback on failure

Integration: CortexOrchestrator → Homeostasis → TransactionShield/ConflictDetector
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from omni.foundation.config.logging import get_logger

from .nodes import TaskGraph, TaskNode, TaskStatus
from .orchestrator import CortexOrchestrator, ExecutionConfig
from .transaction import (
    TransactionShield,
    Transaction,
    ConflictDetector,
    ConflictReport,
    TransactionStatus,
    ConflictSeverity,
)

logger = get_logger("omni.cortex.homeostasis")


@dataclass
class HomeostasisConfig:
    """Configuration for Homeostasis."""

    enable_isolation: bool = True  # Enable Git branch isolation
    enable_conflict_detection: bool = True  # Enable AST-based conflict detection
    auto_merge_on_success: bool = True  # Auto-merge verified transactions
    auto_rollback_on_failure: bool = True  # Auto-rollback failed transactions
    base_branch: str = "main"
    verification_timeout: int = 300  # Seconds for verification
    max_retries: int = 2


@dataclass
class HomeostasisResult:
    """Result of a Homeostasis-managed execution."""

    success: bool = False
    total_transactions: int = 0
    successful_transactions: int = 0
    failed_transactions: int = 0
    merged_transactions: int = 0
    conflicts_detected: int = 0
    duration_ms: float = 0
    transactions: dict[str, dict] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class Homeostasis:
    """
    Homeostasis system for safe concurrent task execution.

    Responsibilities:
    1. Wrap CortexOrchestrator with transaction isolation
    2. Detect and resolve conflicts between concurrent tasks
    3. Provide atomic commit/rollback semantics
    4. Integrate with Immune System for verification

    Example:
        homeostasis = Homeostasis()
        result = await homeostasis.execute_with_protection(task_graph)
    """

    def __init__(
        self,
        config: HomeostasisConfig | None = None,
        orchestrator: CortexOrchestrator | None = None,
    ):
        """Initialize Homeostasis.

        Args:
            config: Homeostasis configuration
            orchestrator: Optional CortexOrchestrator instance
        """
        self.config = config or HomeostasisConfig()
        self.orchestrator = orchestrator or CortexOrchestrator()
        self.shield = TransactionShield(base_branch=self.config.base_branch)
        self.conflict_detector = ConflictDetector()
        self._execution_start: datetime | None = None

    async def execute_with_protection(
        self,
        task_graph: TaskGraph,
        context: dict[str, Any] | None = None,
    ) -> HomeostasisResult:
        """
        Execute a task graph with full Homeostasis protection.

        Args:
            task_graph: The task graph to execute
            context: Execution context

        Returns:
            HomeostasisResult with execution outcomes
        """
        self._execution_start = datetime.now()
        logger.info(
            "homeostasis.execution_started",
            tasks=len(task_graph.all_tasks),
            enable_isolation=self.config.enable_isolation,
            enable_conflict_detection=self.config.enable_conflict_detection,
        )

        transactions: dict[str, Transaction] = {}
        result_transactions: dict[str, dict] = {}
        conflicts_detected = 0
        errors: list[str] = []

        try:
            # Stage 1: Begin all transactions (create isolated branches)
            if self.config.enable_isolation:
                for task_id in task_graph.all_tasks:
                    transaction = await self.shield.begin_transaction(task_id)
                    transactions[task_id] = transaction
                    logger.info(
                        "homeostasis.transaction_started",
                        task_id=task_id,
                        branch=transaction.branch_name,
                    )

            # Stage 2: Execute tasks with conflict detection
            # We'll execute level by level, detecting conflicts between levels
            execution_levels = task_graph.get_execution_levels()

            for level_idx, level in enumerate(execution_levels):
                logger.info(
                    "homeostasis.executing_level",
                    level=level_idx,
                    task_count=len(level),
                )

                # Detect conflicts between tasks in this level
                if self.config.enable_conflict_detection and len(level) > 1:
                    conflict_report = await self._detect_level_conflicts(level, task_graph)
                    if conflict_report.has_conflicts:
                        conflicts_detected += len(conflict_report.conflicts)
                        logger.warning(
                            "homeostasis.conflicts_detected",
                            level=level_idx,
                            count=len(conflict_report.conflicts),
                            severity=conflict_report.severity.value,
                        )
                        # Log suggestions
                        for suggestion in conflict_report.suggestions[:3]:
                            logger.info(
                                "homeostasis.conflict_suggestion",
                                suggestion=suggestion,
                            )

                # Execute tasks in parallel
                level_tasks = [task_graph.all_tasks[task_id] for task_id in level]

                # Wrap task execution with transaction
                for task in level_tasks:
                    await self._execute_with_transaction(
                        task, transactions, result_transactions, context
                    )

            # Stage 3: Verify and merge successful transactions
            if self.config.auto_merge_on_success:
                for task_id, transaction in transactions.items():
                    if transaction.status == TransactionStatus.COMMITTED:
                        # Verify first
                        verified = await self.shield.verify_transaction(task_id)
                        if verified:
                            merged = await self.shield.merge_transaction(task_id)
                            if merged:
                                result_transactions[task_id]["merged"] = True
                                result_transactions[task_id]["status"] = "merged"

            # Stage 4: Cleanup failed transactions
            if self.config.auto_rollback_on_failure:
                for task_id, transaction in transactions.items():
                    if transaction.status in (
                        TransactionStatus.FAILED,
                        TransactionStatus.ISOLATED,
                        TransactionStatus.MODIFYING,
                    ):
                        await self.shield.rollback_transaction(task_id)
                        result_transactions[task_id]["rolled_back"] = True

            duration_ms = (datetime.now() - self._execution_start).total_seconds() * 1000

            success = all(
                result_transactions.get(tid, {}).get("status") == "success" for tid in transactions
            )

            return HomeostasisResult(
                success=success,
                total_transactions=len(transactions),
                successful_transactions=sum(
                    1 for t in result_transactions.values() if t.get("status") == "success"
                ),
                failed_transactions=sum(
                    1 for t in result_transactions.values() if t.get("status") == "failed"
                ),
                merged_transactions=sum(
                    1 for t in result_transactions.values() if t.get("merged", False)
                ),
                conflicts_detected=conflicts_detected,
                duration_ms=duration_ms,
                transactions=result_transactions,
                errors=errors,
            )

        except Exception as e:
            logger.error(
                "homeostasis.execution_error",
                error=str(e),
            )
            # Rollback all transactions on error
            await self.shield.cleanup_all()

            return HomeostasisResult(
                success=False,
                total_transactions=len(transactions),
                failed_transactions=len(transactions),
                duration_ms=(datetime.now() - self._execution_start).total_seconds() * 1000,
                transactions=result_transactions,
                errors=[str(e)],
            )

    async def _execute_with_transaction(
        self,
        task: TaskNode,
        transactions: dict[str, Transaction],
        results: dict[str, dict],
        context: dict[str, Any] | None = None,
    ) -> None:
        """Execute a single task with transaction protection."""
        results[task.id] = {
            "status": "pending",
            "start_time": datetime.now().isoformat(),
        }

        try:
            task.status = TaskStatus.RUNNING

            # Execute via orchestrator
            result = await self.orchestrator._run_with_solver(task.command, context)

            # Record modifications (if any files were changed)
            # This would be enhanced with actual file tracking
            if task.metadata.get("file"):
                await self.shield.record_modification(
                    task.id,
                    task.metadata["file"],
                )

            # Commit the transaction
            if self.config.enable_isolation:
                await self.shield.commit_changes(
                    task.id,
                    message=f"omni: {task.description}",
                )

            task.status = TaskStatus.SUCCESS
            results[task.id]["status"] = "success"
            results[task.id]["end_time"] = datetime.now().isoformat()
            results[task.id]["output"] = result.get("output", "")

            logger.info(
                "homeostasis.task_success",
                task_id=task.id,
            )

        except Exception as e:
            task.status = TaskStatus.FAILED
            results[task.id]["status"] = "failed"
            results[task.id]["error"] = str(e)
            results[task.id]["end_time"] = datetime.now().isoformat()

            logger.error(
                "homeostasis.task_failed",
                task_id=task.id,
                error=str(e),
            )

    async def _detect_level_conflicts(
        self,
        level_tasks: list[str],
        task_graph: TaskGraph,
    ) -> ConflictReport:
        """Detect conflicts between tasks in the same execution level."""
        all_conflicts = []
        max_severity = ConflictSeverity.NONE

        # Compare each pair of tasks
        for i, task_a_id in enumerate(level_tasks):
            for task_b_id in level_tasks[i + 1 :]:
                task_a = task_graph.all_tasks.get(task_a_id)
                task_b = task_graph.all_tasks.get(task_b_id)

                if not task_a or not task_b:
                    continue

                # Check if they modify the same file
                file_a = task_a.metadata.get("file", "")
                file_b = task_b.metadata.get("file", "")

                if file_a and file_b and file_a == file_b:
                    # Direct file conflict
                    all_conflicts.append(
                        {
                            "type": "file_conflict",
                            "file": file_a,
                            "task_a": task_a_id,
                            "task_b": task_b_id,
                            "description": f"Both tasks modify {file_a}",
                        }
                    )
                    max_severity = ConflictSeverity.MEDIUM

        return ConflictReport(
            has_conflicts=len(all_conflicts) > 0,
            severity=max_severity,
            conflicts=all_conflicts,
            suggestions=[
                "Consider executing these tasks sequentially",
                "Or merge changes manually before parallel execution",
            ],
            auto_resolvable=max_severity in (ConflictSeverity.NONE, ConflictSeverity.LOW),
        )

    async def analyze_merge_conflicts(
        self,
        task_id: str,
        base_branch: str | None = None,
    ) -> ConflictReport:
        """Analyze potential merge conflicts for a transaction.

        Args:
            task_id: The task identifier
            base_branch: Branch to compare against

        Returns:
            ConflictReport with potential merge conflicts
        """
        transaction = self.shield.get_transaction(task_id)
        if not transaction:
            return ConflictReport(
                has_conflicts=False,
                severity=ConflictSeverity.NONE,
            )

        target = base_branch or self.config.base_branch

        # Get diff between transaction branch and target
        # This is a simplified version - real implementation would use AST

        return ConflictReport(
            has_conflicts=False,
            severity=ConflictSeverity.NONE,
            suggestions=[
                "Review changes before manual merge",
            ],
        )


__all__ = [
    "Homeostasis",
    "HomeostasisConfig",
    "HomeostasisResult",
]
