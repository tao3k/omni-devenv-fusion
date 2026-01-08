# schema/harvester.py
# Phase 12: The Cycle of Evolution (Harvester)

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class KnowledgeCategory(str, Enum):
    """Categories for harvested knowledge."""

    ARCHITECTURAL_DECISION = "architecture"
    DEBUGGING_CASE = "debugging"
    CODE_PATTERN = "pattern"
    WORKFLOW_RULE = "workflow"


class HarvestedInsight(BaseModel):
    """
    Structure of wisdom distilled from a development session.
    Used by Harvester to crystallize experience into permanent knowledge.
    """

    title: str = Field(..., description="Concise title, e.g., 'Fixing Deadlock in Nested Locks'")
    category: KnowledgeCategory = Field(..., description="Knowledge category")
    context: str = Field(..., description="Problem background or task description")
    solution: str = Field(..., description="The solution that was implemented")
    key_takeaways: List[str] = Field(
        ..., description="Key lessons learned (what went right, what went wrong)"
    )
    code_snippet: Optional[str] = Field(
        None, description="Representative code snippet if applicable"
    )
    related_files: List[str] = Field(
        default_factory=list, description="Files that were modified or created"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Fixing Deadlock in Nested Locks",
                    "category": "debugging",
                    "context": "Multi-threaded counter with nested lock acquisition caused deadlock",
                    "solution": "Used single lock instead of nested locks, or established consistent lock ordering",
                    "key_takeaways": [
                        "Never acquire locks in different orders across different code paths",
                        "Consider using single lock for simple cases",
                        "Deadlock patterns can be detected via code review",
                    ],
                    "code_snippet": "with self._lock_a: with self._lock_b:  # BAD",
                    "related_files": ["src/mcp_server/temp_test.py"],
                }
            ]
        }
    }


__all__ = ["KnowledgeCategory", "HarvestedInsight"]
