# agent/core/schema/__init__.py
"""
 The Neural Matrix - PydanticAI Schema Definitions

Type-safe schemas for RAG-enhanced self-evolving system.
Uses Pydantic for structured AI outputs and LangGraph for workflow state machines.

Lazy loading: Pydantic models are only imported when accessed.
This significantly reduces import time from ~427ms to near-instant.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Literal

# Lazy loading cache
_loaded_schemas: dict = {}
_pydantic_cache: dict = {}


def _get_pydantic():
    """Get Pydantic classes lazily."""
    if "BaseModel" not in _pydantic_cache:
        from pydantic import BaseModel, Field

        _pydantic_cache["BaseModel"] = BaseModel
        _pydantic_cache["Field"] = Field
    return _pydantic_cache


def __getattr__(name: str):
    """Lazy load schema classes on first access."""
    if name in _loaded_schemas:
        return _loaded_schemas[name]

    # Import and cache the class
    mod = _schema_registry.get(name)
    if mod:
        # Import the module using relative import
        from importlib import import_module

        schema_module = import_module(mod, package=__name__)
        # Get the attribute
        obj = getattr(schema_module, name)
        _loaded_schemas[name] = obj
        return obj

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Schema registry - maps class name to module
_schema_registry = {
    # Legislation
    "SpecGapAnalysis": ".legislation",
    "LegislationDecision": ".legislation",
    # Complexity
    "ComplexityLevel": ".complexity",
    "FeatureComplexity": ".complexity",
    # Commit
    "CommitScopeValidation": ".commit",
    "CommitMessageValidation": ".commit",
    "CommitAuthorization": ".commit",
    # Review
    "ReviewFinding": ".review",
    "CodeReviewResult": ".review",
    # Alignment
    "AlignmentCheck": ".alignment",
    "DesignAlignmentResult": ".alignment",
    # Neural Memory
    "MemoryEntry": ".memory",
    "RecallQuery": ".memory",
    "RecallResult": ".memory",
    # Routing
    "RouterDomain": ".routing",
    "RouterSuggestion": ".routing",
    #  Harvester
    "KnowledgeCategory": ".harvester",
    "HarvestedInsight": ".harvester",
    #  Skill
    "SkillDependencies": ".skill",
    "SkillMetadata": ".skill",
}

# Backward compatibility - expose all classes
__all__ = list(_schema_registry.keys())
