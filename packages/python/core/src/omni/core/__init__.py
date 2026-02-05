"""
omni.core - Microkernel Core

Microkernel architecture for agent core:

kernel/        - Core Kernel class, single entry point (includes lifecycle)
components/    - Unified components (registry, orchestrator, loader)
skills/        - Skills system (loader, registry, runtime)

This layer provides:
- Single entry point for agent initialization
- Unified lifecycle management
- Component isolation for clean architecture
"""

from .errors import (
    CoreErrorCode,
    ErrorCategory,
    OmniError,
    OmniCellError,
    SecurityError,
    ToolExecutionError,
    ToolNotFoundError,
    ValidationError,
)
from .executor import CommandExecutor
from .kernel import Kernel, LifecycleManager, LifecycleState, get_kernel
from .responses import ResponseStatus, ToolResponse
from .testing import (
    benchmark,
    cloud,
    e2e,
    get_test_layer,
    integration,
    only_cloud,
    skip_if_cloud,
    stress,
    unit,
)

__all__ = [
    # Error handling
    "CoreErrorCode",
    "ErrorCategory",
    "OmniError",
    "OmniCellError",
    "SecurityError",
    "ToolExecutionError",
    "ToolNotFoundError",
    "ValidationError",
    # Response format
    "ResponseStatus",
    "ToolResponse",
    # Execution
    "CommandExecutor",
    # Kernel
    "Kernel",
    "LifecycleManager",
    "LifecycleState",
    "get_kernel",
    # Testing layers
    "unit",
    "integration",
    "cloud",
    "benchmark",
    "stress",
    "e2e",
    "skip_if_cloud",
    "only_cloud",
    "get_test_layer",
]
