# schema/legislation.py
# Legislation & Spec Management (The Gatekeeper)

from enum import Enum
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class SpecGapAnalysis(BaseModel):
    """Analysis of spec completeness gaps."""

    spec_exists: bool = Field(..., description="Whether spec file exists")
    spec_path: Optional[str] = Field(None, description="Path to spec file if exists")
    completeness_score: int = Field(..., ge=0, le=100, description="Completeness score 0-100")
    missing_sections: List[str] = Field(
        default_factory=list, description="List of missing required sections"
    )
    has_template_placeholders: bool = Field(
        ..., description="Contains unfilled template placeholders"
    )
    test_plan_defined: bool = Field(..., description="Verification plan is present")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "spec_exists": True,
                    "spec_path": "assets/specs/auth_module.md",
                    "completeness_score": 85,
                    "missing_sections": ["Security Considerations"],
                    "has_template_placeholders": False,
                    "test_plan_defined": True,
                }
            ]
        }
    }


class LegislationDecision(BaseModel):
    """Final gatekeeper decision for new work."""

    decision: Literal["allowed", "blocked"] = Field(..., description="Gatekeeper decision")
    reasoning: str = Field(..., description="Why this decision was made")
    required_action: Literal["create_spec", "update_spec", "proceed_to_code", "wait_for_review"] = (
        Field(..., description="What the agent should do next")
    )
    gap_analysis: SpecGapAnalysis = Field(..., description="Detailed gap analysis")
    spec_path: Optional[str] = Field(None, description="Auto-detected spec path")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "decision": "blocked",
                    "reasoning": "Legislation is MANDATORY for new work",
                    "required_action": "create_spec",
                    "gap_analysis": {
                        "spec_exists": False,
                        "spec_path": None,
                        "completeness_score": 0,
                        "missing_sections": ["all"],
                        "has_template_placeholders": False,
                        "test_plan_defined": False,
                    },
                    "spec_path": None,
                }
            ]
        }
    }


__all__ = ["SpecGapAnalysis", "LegislationDecision"]
