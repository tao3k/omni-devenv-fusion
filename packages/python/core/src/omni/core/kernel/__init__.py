"""
omni.core.kernel - Kernel Namespace

Microkernel architecture core:
- Kernel: Main orchestrator
- Components: Registry, Skill Plugin, Skill Loader, MCP Tool Adapter
- Lifecycle: State machine management

Lifecycle Flow (async, ordered):
================================

Stage 1: Lifecycle INIT -> READY (_on_ready)
  Step 1.1: Initialize skill context (instant)
  Step 1.2: Load universal skills from Index (DB read + factory.create)
  Step 1.3: Load each skill's extensions & scripts (may trigger imports)
  Step 1.4: Build Semantic Cortex (embedding + vector DB writes)
  Step 1.5: Load Sniffer rules (DB read)
  Step 1.6: Log summary

Stage 2: Lifecycle READY -> RUNNING (_on_running)
  Step 2.1: Start file watcher (if enabled)
  Step 2.2: Enable skill hot-reload

Critical Path Analysis:
- Fast path: Step 1.1 (instant)
- DB path: Step 1.2, 1.5 (DB reads, cached after first boot)
- CPU path: Step 1.3 (skill.load), Step 1.4 (embedding)
- I/O path: Step 1.4 (vector DB writes)

Usage:
    from omni.core.kernel import Kernel, get_kernel
"""

from .engine import Kernel, get_kernel, reset_kernel
from .lifecycle import LifecycleManager, LifecycleState
from .reactor import KernelReactor, get_reactor, reset_reactor, EventTopic

__all__ = [
    "Kernel",
    "LifecycleManager",
    "LifecycleState",
    "KernelReactor",
    "EventTopic",
    "get_kernel",
    "reset_kernel",
    "get_reactor",
    "reset_reactor",
]
