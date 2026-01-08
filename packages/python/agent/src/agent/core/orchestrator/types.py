"""
agent/core/orchestrator/types.py
Pydantic Shield DTOs for Orchestrator.

ODF-EP v6.0 Pillar A: Frozen models with ConfigDict.
"""

from typing import Dict, Any, Optional, List

from pydantic import BaseModel, ConfigDict, Field


class DispatchParams(BaseModel):
    """Parameters for dispatch operation."""

    model_config = ConfigDict(frozen=True)
    user_query: str
    history: List[Dict[str, Any]] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


class DispatchResult(BaseModel):
    """Result of dispatch operation."""

    model_config = ConfigDict(frozen=True)
    success: bool
    content: str
    agent_name: Optional[str] = None
    confidence: float = 0.0
    cost_usd: float = 0.0
    attempt_count: int = 1


class HiveContext(BaseModel):
    """Additional Hive context for dispatch."""

    model_config = ConfigDict(frozen=True)
    mission_brief: Optional[str] = None
    constraints: List[str] = Field(default_factory=list)
    relevant_files: List[str] = Field(default_factory=list)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    target_agent: Optional[str] = None


__all__ = [
    "DispatchParams",
    "DispatchResult",
    "HiveContext",
]
