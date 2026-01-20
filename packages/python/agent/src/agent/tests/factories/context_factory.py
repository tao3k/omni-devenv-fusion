"""
Context Factory

生成 AgentContext, SessionState, AgentResult 等核心对象的测试数据。

Usage:
    from agent.tests.factories import AgentContextFactory, SessionStateFactory

    context = AgentContextFactory.build()
    state = SessionStateFactory.build()
"""

from typing import Any
from polyfactory.factories.pydantic_factory import ModelFactory

from agent.core.agents.base import AgentContext, AgentResult, AuditResult
from agent.core.session import SessionState, SessionEvent


class AgentContextFactory(ModelFactory[AgentContext]):
    """Factory for generating AgentContext instances."""

    __model__ = AgentContext
    __random_seed__ = 42

    system_prompt = "You are a helpful AI assistant."
    tools = []
    mission_brief = "Complete the assigned task."
    constraints = []
    relevant_files = []
    knowledge_context = ""
    rag_sources = []


class AgentResultFactory(ModelFactory[AgentResult]):
    """Factory for generating AgentResult instances."""

    __model__ = AgentResult
    __random_seed__ = 42

    success = True
    content = ""
    tool_calls = []
    message = ""
    confidence = 0.5
    audit_result = None
    needs_review = False
    rag_sources = []


class SessionStateFactory(ModelFactory[SessionState]):
    """Factory for generating SessionState instances."""

    __model__ = SessionState
    __random_seed__ = 42

    session_id = "test-session-123"
    mission_id = None
    current_agent = None
    attempt_number = 1
    history = []
    telemetry = None  # Will use default from model


class SessionEventFactory(ModelFactory[SessionEvent]):
    """Factory for generating SessionEvent instances."""

    __model__ = SessionEvent
    __random_seed__ = 42

    type = "user"
    source = "user"
    content = "Test event content"
    usage = None
    metadata = None


class AuditResultFactory(ModelFactory[AuditResult]):
    """Factory for generating AuditResult instances."""

    __model__ = AuditResult
    __random_seed__ = 42

    approved = True
    feedback = ""
    confidence = 0.5
    issues_found = []
    suggestions = []
