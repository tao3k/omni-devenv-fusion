# schema/alignment.py
# Design Alignment Verification

from typing import List, Optional

from pydantic import BaseModel, Field


class AlignmentCheck(BaseModel):
    """Result of a single alignment check."""

    aligned: bool = Field(..., description="Whether aligned")
    notes: List[str] = Field(default_factory=list, description="Notes about alignment")
    in_roadmap: Optional[bool] = Field(None, description="If in roadmap (for roadmap check)")


class DesignAlignmentResult(BaseModel):
    """Complete design alignment verification."""

    aligned: bool = Field(..., description="Overall alignment status")
    feature: str = Field(..., description="Feature being verified")
    philosophy: AlignmentCheck = Field(..., description="Philosophy alignment")
    roadmap: AlignmentCheck = Field(..., description="Roadmap alignment")
    architecture: AlignmentCheck = Field(..., description="Architecture alignment")
    recommendations: List[str] = Field(
        default_factory=list, description="Actionable recommendations"
    )


__all__ = ["AlignmentCheck", "DesignAlignmentResult"]
