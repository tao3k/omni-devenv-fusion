"""
Immune system module for evolution security gates.

This package is Rust-first:
- Static scan uses `omni.foundation.bridge.rust_immune.scan_code_security`
- Dynamic simulation uses Rust sandbox integration
- Python code here is an orchestration and compatibility facade only

Quick start:
    from omni.agent.core.evolution.immune import ImmuneSystem

    immune = ImmuneSystem()
    report = await immune.process_candidate(skill_path)
"""

from __future__ import annotations

# Level 1: Static Analysis
from .validator import StaticValidator, SecurityViolation, scan_file, scan_content, quick_check

# Level 2: Dynamic Simulation
from .simulator import SkillSimulator, SimulationResult, verify_skill

# Level 3: System Integration
from .system import ImmuneSystem, ImmuneReport, create_immune_system

# Bridge utilities - import from foundation.bridge directly (not relative)
from omni.foundation.bridge import rust_immune

__all__ = [
    # Level 1
    "StaticValidator",
    "SecurityViolation",
    "scan_file",
    "scan_content",
    "quick_check",
    # Level 2
    "SkillSimulator",
    "SimulationResult",
    "verify_skill",
    # Level 3
    "ImmuneSystem",
    "ImmuneReport",
    "create_immune_system",
    # Bridge
    "rust_immune",
]

__version__ = "1.1.0"
