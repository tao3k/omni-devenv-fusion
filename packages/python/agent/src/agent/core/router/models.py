"""
src/agent/core/router/models.py
Router Models - Data structures for routing decisions.

Phase 14: Models for both Tool Routing (SemanticRouter) and Agent Routing (HiveRouter).

Usage:
    # Models are self-contained, no imports needed
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# =============================================================================
# Phase 14: Tool Routing Models
# =============================================================================


@dataclass
class RoutingResult:
    """
    The complete output of the routing decision (Tool Routing).

    Contains:
    - selected_skills: List of skill names to activate
    - mission_brief: Actionable directive for the Worker
    - reasoning: Audit trail of why these skills were chosen
    - confidence: Routing confidence (0.0-1.0)
    - suggested_skills: Skills found via Vector Fallback (Phase 36.2) - LOCAL only
    - remote_suggestions: Remote skills found that need installation (Phase 36.8)
    - from_cache: Whether this was a cache hit
    - timestamp: When routing decision was made
    - env_snapshot: Environment state from ContextSniffer (Phase 42)
    """

    selected_skills: List[str]
    mission_brief: str
    reasoning: str
    confidence: float = 0.5
    suggested_skills: List[str] = field(default_factory=list)
    remote_suggestions: List[Dict[str, Any]] = field(default_factory=list)  # Phase 36.8
    from_cache: bool = False
    timestamp: float = field(default_factory=time.time)
    env_snapshot: str = ""  # [Phase 42] Environment state snapshot

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skills": self.selected_skills,
            "mission_brief": self.mission_brief,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "suggested_skills": self.suggested_skills,
            "remote_suggestions": self.remote_suggestions,
            "from_cache": self.from_cache,
            "timestamp": self.timestamp,
            "env_snapshot": self.env_snapshot,
        }


# =============================================================================
# Phase 14: Agent Routing Models
# =============================================================================


class Decision(Enum):
    """Possible decisions from agent thinking phase."""

    ACT = "act"  # Execute tool call
    HANDOFF = "handoff"  # Transfer to another agent
    ASK_USER = "ask_user"  # Need clarification
    FINISH = "finish"  # Task complete


class ToolCall(BaseModel):
    """Represents a tool call to be executed."""

    tool: str  # Format: "skill.function_name", e.g., "filesystem.list_directory"
    args: Dict[str, Any] = {}


class TaskBrief(BaseModel):
    """Context passed during agent handoff."""

    task_description: str
    constraints: List[str] = []
    relevant_files: List[str] = []
    previous_attempts: List[str] = []
    success_criteria: List[str] = []


class AgentResponse(BaseModel):
    """Response from agent's thinking phase."""

    decision: Decision
    tool_call: Optional[ToolCall] = None
    handoff_to: Optional[str] = None
    message: str = ""
    confidence: float = 0.5
    timestamp: float = 0.0

    def __init__(self, **data):
        super().__init__(**data)
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class AgentRoute(BaseModel):
    """
    Result of agent routing decision (Agent Routing).

    Contains:
    - target_agent: Which agent should handle this request
    - confidence: How confident the routing decision is
    - reasoning: Why this agent was chosen
    - task_brief: Commander's Intent for the agent (Phase 14)
    - constraints: List of constraints for the task
    - relevant_files: Files relevant to the task
    - from_cache: Whether this was a cache hit (Phase 18)
    """

    target_agent: str  # "coder", "reviewer", "orchestrator"
    confidence: float = 0.5
    reasoning: str
    task_brief: str = ""
    constraints: List[str] = []
    relevant_files: List[str] = []
    from_cache: bool = False  # Phase 18: Cache hit indicator


# =============================================================================
# Agent Persona Definitions (Used by HiveRouter)
# =============================================================================

AGENT_PERSONAS = {
    "coder": {
        "description": "Primary Executor. Writes code, refactors, fixes bugs, implements features.",
        "keywords": [
            "write",
            "create",
            "implement",
            "refactor",
            "fix",
            "edit",
            "modify",
            "add function",
            "new file",
        ],
        "skills": ["filesystem", "software_engineering", "terminal", "testing"],
    },
    "reviewer": {
        "description": "Quality Gatekeeper. Reviews changes, runs tests, checks git status, commits code.",
        "keywords": [
            "review",
            "check",
            "test",
            "verify",
            "commit",
            "git",
            "diff",
            "status",
            "run tests",
            "lint",
        ],
        "skills": ["git", "testing", "linter"],
    },
    "orchestrator": {
        "description": "The Manager. Plans tasks, explains concepts, manages context, handles ambiguity.",
        "keywords": [
            "plan",
            "explain",
            "how to",
            "what is",
            "analyze",
            "breakdown",
            "help",
            "understand",
            "context",
        ],
        "skills": ["context", "spec", "router", "knowledge"],
    },
}
