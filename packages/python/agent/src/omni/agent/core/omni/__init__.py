"""
omni - CCA Loop Implementation with Context Optimization (Token Diet)

A modular ReAct (Reasoning + Acting) loop for intelligent task execution.

Modules:
- config: Configuration dataclasses
- logging: Pretty console output helpers
- schemas: Tool schema extraction from handlers
- react: Simple ReAct workflow implementation
- loop: Main OmniLoop orchestrator
- omega: Project Omega - Unified Hub for all subsystems

Usage:
    from omni.agent.core.omni import OmniLoop, OmniLoopConfig

    loop = OmniLoop()
    result = await loop.run("Your task here")

Omega (Unified Hub):
    from omni.agent.core.omni import OmegaRunner, MissionConfig

    runner = OmegaRunner()
    result = await runner.run_mission("Your complex goal")
"""

from .config import OmniLoopConfig
from .loop import OmniLoop
from .react import ReActWorkflow
from .omega import (
    OmegaRunner,
    OMEGA_TOPICS,
    MissionConfig,
    MissionResult,
    RecoveryNode,
    CortexDashboard,
    OmegaDashboard,
)

__all__ = [
    "OmniLoop",
    "OmniLoopConfig",
    "ReActWorkflow",
    # Omega
    "OmegaRunner",
    "OMEGA_TOPICS",  # Event topic constants matching omni-events
    "MissionConfig",
    "MissionResult",
    "RecoveryNode",
    "CortexDashboard",
    "OmegaDashboard",
]
