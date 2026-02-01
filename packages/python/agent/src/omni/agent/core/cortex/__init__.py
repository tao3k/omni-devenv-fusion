"""
cortex.py - Prefrontal Cortex Module

Parallel task orchestration and dynamic sub-graph dispatch.

Components:
- nodes: TaskNode, TaskGroup, TaskGraph
- planner: TaskDecomposer for goal decomposition
- orchestrator: CortexOrchestrator for parallel execution
- transaction: TransactionShield for Git isolation
- homeostasis: Homeostasis integration layer

Integration:
    TaskDecomposer → CortexOrchestrator → TransactionShield → OmniCell
                                              ↓
                                    Homeostasis (Conflict Detection)
"""

from .nodes import (
    TaskNode,
    TaskGroup,
    TaskGraph,
    TaskStatus,
    TaskPriority,
)

from .planner import (
    TaskDecomposer,
    DecompositionResult,
    FileAnalysis,
)

from .orchestrator import (
    CortexOrchestrator,
    ExecutionConfig,
    ExecutionResult,
)

from .transaction import (
    TransactionShield,
    Transaction,
    TransactionStatus,
    ConflictDetector,
    ConflictReport,
    ConflictSeverity,
)

from .homeostasis import (
    Homeostasis,
    HomeostasisConfig,
    HomeostasisResult,
)

__all__ = [
    # Nodes
    "TaskNode",
    "TaskGroup",
    "TaskGraph",
    "TaskStatus",
    "TaskPriority",
    # Planner
    "TaskDecomposer",
    "DecompositionResult",
    "FileAnalysis",
    # Orchestrator
    "CortexOrchestrator",
    "ExecutionConfig",
    "ExecutionResult",
    # Transaction
    "TransactionShield",
    "Transaction",
    "TransactionStatus",
    "ConflictDetector",
    "ConflictReport",
    "ConflictSeverity",
    # Homeostasis
    "Homeostasis",
    "HomeostasisConfig",
    "HomeostasisResult",
]
