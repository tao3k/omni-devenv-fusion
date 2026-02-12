"""
evolution - Self-Evolution Module

Dual-Path Evolution Architecture:
- Fast Path: Semantic Memory (System 1 - 快速思考)
- Slow Path: Procedural Skills (System 2 - 慢思考)

Modules:
- tracer: Execution trace collection (OmniCell → Evolution)
- universal_solver: Integration bridge (Core OmniCell → Evolution)
- manager: Orchestration layer (coordinates all components)
- harvester: Session analysis & skill extraction
- factory: Automated skill synthesis
- schemas: Data models for skill crystallization
- prompts: LLM prompts for skill extraction
- immune: Security defense orchestration (Rust scan/sandbox backends)

Usage:
    from omni.agent.core.evolution.tracer import TraceCollector, ExecutionTrace
    from omni.agent.core.evolution.universal_solver import UniversalSolver, SolverResult, SolverStatus
    from omni.agent.core.evolution.manager import EvolutionManager, EvolutionConfig, CrystallizationCandidate
    from omni.agent.core.evolution.harvester import Harvester, CandidateSkill, process_trace_for_skill
    from omni.agent.core.evolution.factory import SkillFactory, create_skill_from_candidate
    from omni.agent.core.evolution.schemas import CandidateSkill, CrystallizationResult
    from omni.agent.core.evolution.immune import ImmuneSystem
"""

from .harvester import Harvester, process_trace_for_skill
from .factory import SkillFactory, CrystallizationResult
from .tracer import ExecutionTrace, TraceCollector
from .universal_solver import UniversalSolver, SolverResult, SolverStatus
from .manager import EvolutionManager, EvolutionConfig, EvolutionState, CrystallizationCandidate
from .schemas import CandidateSkill
from .prompts import (
    SKILL_EXTRACTION_PROMPT,
    XML_GUIDE_TEMPLATE,
    render_xml_guide,
)

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
    # Core Types
    "ExecutionTrace",
    "TraceCollector",
    # Solver Integration
    "UniversalSolver",
    "SolverResult",
    "SolverStatus",
    # Orchestration
    "EvolutionManager",
    "EvolutionConfig",
    "EvolutionState",
    "CrystallizationCandidate",
    # Skill Creation
    "Harvester",
    "process_trace_for_skill",
    "SkillFactory",
    "CrystallizationResult",
    # Data Models
    "CandidateSkill",
    # Prompts & XML
    "SKILL_EXTRACTION_PROMPT",
    "XML_GUIDE_TEMPLATE",
    "render_xml_guide",
    # Immune System
    "ImmuneSystem",
    "ImmuneReport",
    "StaticValidator",
    "SecurityViolation",
    "SkillSimulator",
    "SimulationResult",
]
