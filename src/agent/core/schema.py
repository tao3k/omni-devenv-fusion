# agent/core/schema.py
"""
Phase 11: The Neural Matrix - PydanticAI Schema Definitions

Type-safe schemas for RAG-enhanced self-evolving system.
Uses Pydantic for structured AI outputs and LangGraph for workflow state machines.

Schemas:
- LegislationDecision: Gatekeeper decision (allowed/blocked)
- SpecGapAnalysis: Spec completeness analysis
- FeatureComplexity: L1-L4 complexity assessment
- CommitValidation: Smart commit authorization
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# =============================================================================
# Legislation & Spec Management (The Gatekeeper)
# =============================================================================

class SpecGapAnalysis(BaseModel):
    """Analysis of spec completeness gaps."""
    spec_exists: bool = Field(..., description="Whether spec file exists")
    spec_path: Optional[str] = Field(None, description="Path to spec file if exists")
    completeness_score: int = Field(..., ge=0, le=100, description="Completeness score 0-100")
    missing_sections: List[str] = Field(
        default_factory=list,
        description="List of missing required sections"
    )
    has_template_placeholders: bool = Field(
        ..., description="Contains unfilled template placeholders"
    )
    test_plan_defined: bool = Field(..., description="Verification plan is present")

    class Config:
        json_schema_extra = {
            "examples": [{
                "spec_exists": True,
                "spec_path": "agent/specs/auth_module.md",
                "completeness_score": 85,
                "missing_sections": ["Security Considerations"],
                "has_template_placeholders": False,
                "test_plan_defined": True
            }]
        }


class LegislationDecision(BaseModel):
    """Final gatekeeper decision for new work."""
    decision: Literal["allowed", "blocked"] = Field(
        ..., description="Gatekeeper decision"
    )
    reasoning: str = Field(..., description="Why this decision was made")
    required_action: Literal[
        "create_spec", "update_spec", "proceed_to_code", "wait_for_review"
    ] = Field(..., description="What the agent should do next")
    gap_analysis: SpecGapAnalysis = Field(..., description="Detailed gap analysis")
    spec_path: Optional[str] = Field(None, description="Auto-detected spec path")

    class Config:
        json_schema_extra = {
            "examples": [{
                "decision": "blocked",
                "reasoning": "Legislation is MANDATORY for new work",
                "required_action": "create_spec",
                "gap_analysis": {
                    "spec_exists": False,
                    "spec_path": None,
                    "completeness_score": 0,
                    "missing_sections": ["all"],
                    "has_template_placeholders": False,
                    "test_plan_defined": False
                },
                "spec_path": None
            }]
        }


# =============================================================================
# Complexity Assessment (Feature Lifecycle)
# =============================================================================

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
        default_factory=list,
        description="Examples of this complexity level"
    )

    class Config:
        json_schema_extra = {
            "examples": [{
                "level": "L2",
                "name": "Minor",
                "definition": "New utility function, minor tweak",
                "rationale": "Single Python file modified, no new modules",
                "test_requirements": "just test-unit",
                "examples": ["Add helper function", "Refactor internal method"]
            }]
        }


# =============================================================================
# Commit Authorization (Smart Commit Protocol)
# =============================================================================

class CommitScopeValidation(BaseModel):
    """Validation result for commit scope."""
    scope: str = Field(..., description="Commit scope being validated")
    is_valid: bool = Field(..., description="Whether scope is valid in cog.toml")
    available_scopes: List[str] = Field(
        default_factory=list,
        description="List of valid scopes from cog.toml"
    )
    suggestion: Optional[str] = Field(
        None,
        description="Closest valid scope if current is invalid"
    )


class CommitMessageValidation(BaseModel):
    """Complete commit message validation."""
    type: str = Field(..., description="Commit type (feat, fix, chore, etc.)")
    scope: str = Field(..., description="Commit scope")
    message: str = Field(..., description="Commit message body")
    is_valid: bool = Field(..., description="Whether message is valid")
    subject_length: int = Field(..., description="Subject line length")
    subject_valid: bool = Field(..., description="Subject follows conventional commits")
    errors: List[str] = Field(
        default_factory=list,
        description="List of validation errors"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of warnings"
    )


class CommitAuthorization(BaseModel):
    """Authorization token for smart commit."""
    auth_token: str = Field(
        ..., description="One-time authorization token"
    )
    expires_at: str = Field(..., description="Token expiration timestamp")
    commit_details: CommitMessageValidation = Field(
        ..., description="Validated commit details"
    )
    instructions: str = Field(..., description="Authorization instructions")


# =============================================================================
# Code Review (The Immune System)
# =============================================================================

class ReviewFinding(BaseModel):
    """Individual code review finding."""
    category: Literal["style", "security", "complexity", "docs", "logic"] = Field(
        ..., description="Finding category"
    )
    severity: Literal["blocker", "critical", "warning", "info"] = Field(
        ..., description="Finding severity"
    )
    file: str = Field(..., description="File with issue")
    line: Optional[int] = Field(None, description="Line number if applicable")
    message: str = Field(..., description="Finding description")
    reference: Optional[str] = Field(
        None,
        description="Standard or rule being violated"
    )
    suggestion: Optional[str] = Field(
        None,
        description="How to fix the issue"
    )


class CodeReviewResult(BaseModel):
    """Complete code review result."""
    verdict: Literal["approve", "request_changes", "reject"] = Field(
        ..., description="Review verdict"
    )
    findings: List[ReviewFinding] = Field(
        default_factory=list,
        description="All review findings"
    )
    summary: str = Field(..., description="Human-readable summary")
    blocked_by: List[str] = Field(
        default_factory=list,
        description="Blocker categories if changes requested"
    )
    standards_checked: List[str] = Field(
        default_factory=list,
        description="Which standards were checked"
    )


# =============================================================================
# Design Alignment Verification
# =============================================================================

class AlignmentCheck(BaseModel):
    """Result of a single alignment check."""
    aligned: bool = Field(..., description="Whether aligned")
    notes: List[str] = Field(
        default_factory=list,
        description="Notes about alignment"
    )
    in_roadmap: Optional[bool] = Field(
        None,
        description="If in roadmap (for roadmap check)"
    )


class DesignAlignmentResult(BaseModel):
    """Complete design alignment verification."""
    aligned: bool = Field(..., description="Overall alignment status")
    feature: str = Field(..., description="Feature being verified")
    philosophy: AlignmentCheck = Field(..., description="Philosophy alignment")
    roadmap: AlignmentCheck = Field(..., description="Roadmap alignment")
    architecture: AlignmentCheck = Field(..., description="Architecture alignment")
    recommendations: List[str] = Field(
        default_factory=list,
        description="Actionable recommendations"
    )


# =============================================================================
# RAG Neural Memory (Phase 11 New)
# =============================================================================

class MemoryEntry(BaseModel):
    """A single memory entry in the neural matrix."""
    key: str = Field(..., description="Memory key/identifier")
    value: str = Field(..., description="Memory content")
    category: Literal[
        "decision", "pattern", "error", "context", "preference"
    ] = Field(..., description="Memory category")
    embedding: Optional[List[float]] = Field(
        None,
        description="Vector embedding (for RAG retrieval)"
    )
    source: str = Field(..., description="Where this memory came from")
    timestamp: str = Field(..., description="When this was recorded")
    access_count: int = Field(
        default=0,
        description="Times this memory has been accessed"
    )


class RecallQuery(BaseModel):
    """Query to neural memory system."""
    query: str = Field(..., description="Natural language query")
    category: Optional[str] = Field(
        None,
        description="Filter by category"
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Max results to return"
    )


class RecallResult(BaseModel):
    """Result from neural memory recall."""
    query: str = Field(..., description="Original query")
    memories: List[MemoryEntry] = Field(
        default_factory=list,
        description="Retrieved memories"
    )
    relevance_scores: List[float] = Field(
        default_factory=list,
        description="Relevance scores for each memory"
    )
    source: str = Field(default="neural_matrix", description="System source")


# =============================================================================
# Tool Routing (The Cortex)
# =============================================================================

class RouterDomain(str, Enum):
    """Tool domain classifications."""
    GITOPS = "GitOps"
    PRODUCT_OWNER = "ProductOwner"
    CODER = "Coder"
    QA = "QA"
    MEMORY = "Memory"
    DEVOPS = "DevOps"
    SEARCH = "Search"


class RouterSuggestion(BaseModel):
    """Tool routing suggestion from Cortex."""
    domain: RouterDomain = Field(..., description="Recommended domain")
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence score 0-1"
    )
    reasoning: str = Field(..., description="Why this domain was chosen")
    suggested_tools: List[str] = Field(
        default_factory=list,
        description="Recommended tools in this domain"
    )


# =============================================================================
# Export
# =============================================================================

__all__ = [
    # Legislation
    "SpecGapAnalysis",
    "LegislationDecision",
    # Complexity
    "ComplexityLevel",
    "FeatureComplexity",
    # Commit
    "CommitScopeValidation",
    "CommitMessageValidation",
    "CommitAuthorization",
    # Review
    "ReviewFinding",
    "CodeReviewResult",
    # Alignment
    "AlignmentCheck",
    "DesignAlignmentResult",
    # Neural Memory
    "MemoryEntry",
    "RecallQuery",
    "RecallResult",
    # Routing
    "RouterDomain",
    "RouterSuggestion",
]
