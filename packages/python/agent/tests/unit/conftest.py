"""
conftest.py - Pytest Configuration and Shared Fixtures for Agent Tests

Provides common fixtures for testing OmniLoop, ContextManager, and CLI commands.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_inference_client():
    """
    Create a mock InferenceClient for testing OmniLoop without actual LLM calls.

    Usage:
        async def test_example(mock_inference_client):
            with patch("omni.agent.core.omni.InferenceClient", return_value=mock_inference_client):
                loop = OmniLoop()
                result = await loop.run("Test task")
                assert result == "Mock response"
    """
    mock = MagicMock()
    mock.complete = AsyncMock(
        return_value={
            "success": True,
            "content": "Mock LLM response for testing.",
            "tool_calls": [],
            "model": "sonnet",
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "error": "",
        }
    )
    return mock


@pytest.fixture
def mock_inference_client_with_content(content="Mock response"):
    """
    Create a mock InferenceClient with custom response content.

    Usage:
        async def test_with_custom_response(mock_inference_client_with_content):
            mock_inference_client_with_content.complete.return_value = {
                "success": True,
                "content": "Custom response",
                ...
            }
            ...
    """
    mock = MagicMock()
    mock.complete = AsyncMock(
        return_value={
            "success": True,
            "content": content,
            "tool_calls": [],
            "model": "sonnet",
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "error": "",
        }
    )
    return mock


@pytest.fixture
def mock_failing_inference():
    """
    Create a mock InferenceClient that simulates LLM failure.

    Usage:
        async def test_failure_handling(mock_failing_inference):
            with patch("omni.agent.core.omni.InferenceClient", return_value=mock_failing_inference):
                loop = OmniLoop()
                result = await loop.run("Test")
                assert result == ""
    """
    mock = MagicMock()
    mock.complete = AsyncMock(
        return_value={
            "success": False,
            "content": "",
            "error": "Simulated LLM failure",
        }
    )
    return mock


@pytest.fixture
def sample_system_prompt():
    """Sample system prompt for testing."""
    return "You are Omni-Dev Fusion, an AI development assistant."


@pytest.fixture
def sample_user_message():
    """Sample user message for testing."""
    return "Help me fix the bug in the authentication module."


@pytest.fixture
def sample_llm_response():
    """Sample LLM response for testing."""
    return {
        "success": True,
        "content": "I've analyzed the authentication module and found the issue...",
        "tool_calls": [],
        "model": "sonnet",
        "usage": {"input_tokens": 200, "output_tokens": 150},
        "error": "",
    }


class MockInferenceContext:
    """
    Helper class for testing LLM context passing.

    Captures the arguments passed to complete() for verification.
    """

    def __init__(self):
        self.last_call = None
        self.call_count = 0

    async def complete(self, **kwargs):
        """Mock complete that captures arguments."""
        self.last_call = kwargs
        self.call_count += 1
        return {
            "success": True,
            "content": f"Response {self.call_count}",
            "tool_calls": [],
            "model": "sonnet",
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "error": "",
        }

    def get_last_system_prompt(self):
        """Get the system prompt from the last call."""
        if self.last_call:
            return self.last_call.get("system_prompt")
        return None

    def get_last_user_query(self):
        """Get the user query from the last call."""
        if self.last_call:
            return self.last_call.get("user_query")
        return None


@pytest.fixture
def mock_inference_context():
    """
    Create a mock InferenceClient that captures context for verification.

    Usage:
        async def test_context_passed(mock_inference_context):
            with patch("omni.agent.core.omni.InferenceClient", return_value=mock_inference_context):
                loop = OmniLoop()
                await loop.run("Test task")
                assert mock_inference_context.get_last_user_query() == "Test task"
    """
    return MockInferenceContext()


def create_mock_librarian(search_results=None):
    """
    Create a mock Librarian for RAG-related testing.

    Args:
        search_results: List of search results to return (default: empty list)

    Returns:
        Mock Librarian with search method
    """
    mock = MagicMock()
    mock.is_ready = True
    mock.search = AsyncMock(return_value=search_results or [])
    return mock


@pytest.fixture
def empty_librarian():
    """Create a mock Librarian with no search results."""
    return create_mock_librarian([])


@pytest.fixture
def populated_librarian():
    """Create a mock Librarian with sample search results."""
    # Lazy import to avoid collection-time errors
    try:
        from omni.core.knowledge.librarian import KnowledgeEntry, SearchResult

        entry = KnowledgeEntry(
            id="test_001",
            content="Sample knowledge content",
            source="docs/test.md",
            metadata={},
            score=0.9,
        )
        search_result = SearchResult(entry=entry, score=0.9)
        return create_mock_librarian([search_result])
    except ImportError:
        # Fallback if KnowledgeEntry/SearchResult not available
        return create_mock_librarian([{"id": "test_001", "content": "Sample content"}])
