"""
omni.core.kernel - Kernel Namespace

Microkernel architecture core:
- Kernel: Main orchestrator (renamed from kernel.py to engine.py)
- Components: Registry, Skill Plugin, Skill Loader, MCP Tool Adapter
- Lifecycle: State machine management

Usage:
    from omni.core.kernel import Kernel, get_kernel
"""

from .engine import Kernel, get_kernel, reset_kernel
from .lifecycle import LifecycleManager, LifecycleState

__all__ = [
    "Kernel",
    "LifecycleManager",
    "LifecycleState",
    "get_kernel",
    "reset_kernel",
]
