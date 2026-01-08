# schema/routing.py
# Tool Routing (The Cortex)

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


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
    confidence: float = Field(..., ge=0, le=1, description="Confidence score 0-1")
    reasoning: str = Field(..., description="Why this domain was chosen")
    suggested_tools: List[str] = Field(
        default_factory=list, description="Recommended tools in this domain"
    )


__all__ = ["RouterDomain", "RouterSuggestion"]
