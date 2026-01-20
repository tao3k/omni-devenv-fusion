"""
Factory Extension - Meta-Agent Adaptation Factory

A self-contained extension for skill generation, validation, and harvesting.
Lives in assets/skills/skill/extensions/factory/

This module exposes the main interfaces for the CLI plugin to consume.
"""

from .core import MetaAgent, generate_skill, harvest_skills
from .result import GenerationResult
from .validator import SandboxValidator, ValidationResult, validate_and_refine

__all__ = [
    "MetaAgent",
    "generate_skill",
    "harvest_skills",
    "GenerationResult",
    "SandboxValidator",
    "ValidationResult",
    "validate_and_refine",
]
