# schema/review.py
# Code Review (The Immune System)

from typing import List, Optional

from pydantic import BaseModel, Field


class ReviewFinding(BaseModel):
    """Individual code review finding."""

    category: str = Field(..., description="Finding category")
    severity: str = Field(..., description="Finding severity")
    file: str = Field(..., description="File with issue")
    line: Optional[int] = Field(None, description="Line number if applicable")
    message: str = Field(..., description="Finding description")
    reference: Optional[str] = Field(None, description="Standard or rule being violated")
    suggestion: Optional[str] = Field(None, description="How to fix the issue")


class CodeReviewResult(BaseModel):
    """Complete code review result."""

    verdict: str = Field(..., description="Review verdict")
    findings: List[ReviewFinding] = Field(default_factory=list, description="All review findings")
    summary: str = Field(..., description="Human-readable summary")
    blocked_by: List[str] = Field(
        default_factory=list, description="Blocker categories if changes requested"
    )
    standards_checked: List[str] = Field(
        default_factory=list, description="Which standards were checked"
    )


__all__ = ["ReviewFinding", "CodeReviewResult"]
