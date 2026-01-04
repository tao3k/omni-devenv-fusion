"""
src/agent/core/agents/__init__.py
Agent Package - Specialist Agents for The Hive.

Agents:
- BaseAgent: Abstract base with context injection and tool loading
- CoderAgent: Primary Executor - writes code, refactors, fixes bugs
- ReviewerAgent: Quality Gatekeeper - reviews, tests, commits

Usage:
    from agent.core.agents import CoderAgent, ReviewerAgent, BaseAgent
"""

from agent.core.agents.base import (
    BaseAgent,
    AgentContext,
    AgentResult,
)
from agent.core.agents.coder import CoderAgent
from agent.core.agents.reviewer import ReviewerAgent

__all__ = [
    "BaseAgent",
    "AgentContext",
    "AgentResult",
    "CoderAgent",
    "ReviewerAgent",
]
