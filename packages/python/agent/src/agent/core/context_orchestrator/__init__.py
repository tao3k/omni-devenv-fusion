"""
agent/core/context_orchestrator/__init__.py
Step 4: Async Trinity Orchestrator.

This module has been refactored into modular structure:
- orchestrator.py: Main ContextOrchestrator class
- layers/: Individual layer implementations

Backward compatibility maintained - import from here still works.
"""

from __future__ import annotations

# Re-export for backward compatibility
from .orchestrator import (
    ContextOrchestrator,
    get_context_orchestrator,
    build_context,
)

# Re-export layers for backward compatibility
from .layers import (
    ContextLayer,
    Layer1_SystemPersona,
    Layer2_AvailableSkills,
    Layer3_Knowledge,
    Layer4_AssociativeMemories,
    Layer5_Environment,
    Layer6_CodeMaps,
    Layer7_RawCode,
    Layer1_5_SkillMemory,
)

__all__ = [
    # Main classes
    "ContextOrchestrator",
    "get_context_orchestrator",
    "build_context",
    # Layers
    "ContextLayer",
    "Layer1_SystemPersona",
    "Layer2_AvailableSkills",
    "Layer3_Knowledge",
    "Layer4_AssociativeMemories",
    "Layer5_Environment",
    "Layer6_CodeMaps",
    "Layer7_RawCode",
    "Layer1_5_SkillMemory",
]
