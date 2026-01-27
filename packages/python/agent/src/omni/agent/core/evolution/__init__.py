"""
evolution - Self-Evolution Module

Dual-Path Evolution Architecture:
- Fast Path: Semantic Memory (System 1 - 快速思考)
- Slow Path: Procedural Skills (System 2 - 慢思考)

Modules:
- harvester: Session analysis & skill extraction
- factory: Automated skill synthesis
- immune: Security defense (Rust: omni-ast + omni-security)

Usage:
    from omni.agent.core.evolution.harvester import Harvester, CandidateSkill
    from omni.agent.core.evolution.factory import SkillFactory
    from omni.agent.core.evolution.immune import ImmuneSystem, StaticValidator, SkillSimulator
"""

from .harvester import Harvester, CandidateSkill
from .factory import SkillFactory

# Immune System (Rust Integration)
from .immune import (
    ImmuneSystem,
    ImmuneReport,
    StaticValidator,
    SecurityViolation,
    SkillSimulator,
    SimulationResult,
)

__all__ = [
    "Harvester",
    "CandidateSkill",
    "SkillFactory",
    # Immune System
    "ImmuneSystem",
    "ImmuneReport",
    "StaticValidator",
    "SecurityViolation",
    "SkillSimulator",
    "SimulationResult",
]
