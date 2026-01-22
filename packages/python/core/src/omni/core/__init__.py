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

from .kernel import Kernel, LifecycleManager, LifecycleState, get_kernel

__all__ = [
    "Kernel",
    "get_kernel",
    "LifecycleState",
    "LifecycleManager",
]
