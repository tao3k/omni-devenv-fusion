# schema/complexity.py
# Complexity Assessment (Feature Lifecycle)

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ComplexityLevel(str, Enum):
    """L1-L4 complexity levels per feature-lifecycle.md."""

    L1 = "L1"  # Trivial: Typos, config tweaks, doc updates
    L2 = "L2"  # Minor: New utility function, minor tweak
    L3 = "L3"  # Major: New module, API, DB schema change
    L4 = "L4"  # Critical: Auth, Payments, breaking changes


class FeatureComplexity(BaseModel):
    """Complete complexity assessment result."""

    level: ComplexityLevel = Field(..., description="Complexity level L1-L4")
    name: str = Field(..., description="Human-readable name")
    definition: str = Field(..., description="What this level means")
    rationale: str = Field(..., description="Why this level was assigned")
    test_requirements: str = Field(..., description="Required tests for this level")
    examples: List[str] = Field(
        default_factory=list, description="Examples of this complexity level"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "level": "L2",
                    "name": "Minor",
                    "definition": "New utility function, minor tweak",
                    "rationale": "Single Python file modified, no new modules",
                    "test_requirements": "just test-unit",
                    "examples": ["Add helper function", "Refactor internal method"],
                }
            ]
        }
    }


__all__ = ["ComplexityLevel", "FeatureComplexity"]
