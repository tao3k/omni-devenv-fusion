"""
Context Factory

生成 AgentContext 和相关对象的测试数据。
"""

from typing import Any
from polyfactory.factories.pydantic_factory import ModelFactory


class AgentContextFactory(ModelFactory):
    """Factory for generating AgentContext instances.

    Note: Replace with actual AgentContext import when available.
    """

    __model__: Any = None  # Set to actual model class when available

    # Placeholder fields - will be replaced with actual model
    session_id = "test-session-123"
    user_id = "test-user-456"
    working_directory = "/tmp/test"
    environment = "development"


class SessionStateFactory(ModelFactory):
    """Factory for generating session state objects."""

    __model__: Any = None  # Set to actual model class when available

    session_id = "test-session-123"
    created_at = "2024-01-01T00:00:00Z"
    last_activity = "2024-01-01T00:00:00Z"
    state = {"active_skills": [], "context": {}}


class ConversationContextFactory(ModelFactory):
    """Factory for generating conversation context objects."""

    __model__: Any = None  # Set to actual model class when available

    conversation_id = "conv-123"
    messages = []
    current_skill = None
    history = []


# =============================================================================
# Documentation Examples
# =============================================================================
"""
Usage Examples:

# 1. Basic usage
def test_context_has_required_fields():
    from agent.tests.factories import AgentContextFactory
    context = AgentContextFactory.build()
    assert context.session_id is not None

# 2. With overrides
def test_context_with_custom_session():
    from agent.tests.factories import AgentContextFactory
    context = AgentContextFactory.build(session_id="my-custom-session")
    assert context.session_id == "my-custom-session"
"""
