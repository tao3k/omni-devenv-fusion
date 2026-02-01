"""
Hippocampus Pydantic Models

Data models for long-term memory storage and retrieval.
Correspond to trace.schema.json and experience.schema.json.

Integration:
- HippocampusTrace: Execution trace with full causal chain
- ExperienceMetadata: Indexed metadata for filtered retrieval
- ExperienceRecallResult: Retrieval result with similarity score
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExecutionStep(BaseModel):
    """A single execution step within a trace."""

    command: str = Field(..., description="Command that was executed")
    output: str = Field(default="", description="Command output")
    success: bool = Field(..., description="Whether the step succeeded")
    duration_ms: float = Field(default=0.0, ge=0, description="Step duration in milliseconds")


class HippocampusTrace(BaseModel):
    """Complete task execution trace with environment snapshot and causal chain.

    Represents a successful execution experience that can be recalled
    to guide future similar tasks.
    """

    trace_id: str = Field(..., description="Unique identifier (UUID)")
    task_description: str = Field(..., description="Task description")
    steps: list[ExecutionStep] = Field(..., description="Execution steps with commands and outputs")
    env_fingerprint: dict[str, Any] = Field(
        default_factory=dict,
        description="Environment fingerprint: directory structure, key config states",
    )
    total_duration_ms: float = Field(
        default=0.0, ge=0, description="Total execution duration in ms"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Trace creation timestamp"
    )
    success: bool = Field(..., description="Whether the execution was successful")
    domain: str = Field(
        default="general", description="Domain: file_manipulation, git, test, search"
    )
    nu_pattern: str = Field(default="", description="Core Nu command pattern: ls|where|save")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ExperienceMetadata(BaseModel):
    """Experience metadata for multi-dimensional filtered retrieval.

    Stored alongside the trace in the vector store for efficient filtering.
    Only successful experiences are stored in long-term memory.
    """

    type: str = Field(default="experience_trace", description="Type discriminator")
    trace_id: str = Field(..., description="Reference to the original trace")
    domain: str = Field(..., description="Domain category: file_manipulation | git | test | search")
    nu_pattern: str = Field(default="", description="Nu script skeleton pattern")
    complexity: str = Field(default="low", description="Task complexity level: low | medium | high")
    success: bool = Field(True, description="Only successful experiences are stored")
    tags: list[str] = Field(default_factory=list, description="Custom tags for filtering")
    task_description: str = Field(default="", description="Normalized task description")


class ExperienceRecallResult(BaseModel):
    """Result from recalling experiences from long-term memory."""

    trace_id: str = Field(..., description="Reference to the trace")
    task_description: str = Field(..., description="Task description from the trace")
    similarity_score: float = Field(..., ge=0, le=1, description="Similarity score (0-1)")
    domain: str = Field(default="general", description="Domain of the experience")
    nu_pattern: str = Field(default="", description="Nu command pattern from the experience")
    tags: list[str] = Field(default_factory=list, description="Tags from the experience")
    steps: list[ExecutionStep] = Field(
        default_factory=list, description="Steps from the original trace"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


__all__ = [
    "ExecutionStep",
    "HippocampusTrace",
    "ExperienceMetadata",
    "ExperienceRecallResult",
]
