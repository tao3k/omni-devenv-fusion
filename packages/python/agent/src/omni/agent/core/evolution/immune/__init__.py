"""
immune.py - Immune System Module

Production-grade immune defense for auto-generated skills.

Level 1: Static Analysis (Rust: omni-ast via ast-grep)
Level 2: Dynamic Simulation (Rust: omni-security via Docker/NsJail)
Level 3: Permission Gatekeeping (Rust: omni-security Zero Trust)

Quick Start:
    from omni.agent.core.evolution.immune import ImmuneSystem, StaticValidator, SkillSimulator

    # Full immune system with all defenses
    immune = ImmuneSystem()
    report = await immune.process_candidate(skill_path)

    # Just static analysis
    is_safe, violations = StaticValidator.scan(skill_path)

    # Just sandbox simulation
    result = await SkillSimulator().verify_skill(skill_path)
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

__version__ = "1.0.0"
