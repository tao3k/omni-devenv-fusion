"""
Fake LLM Inference for Testing.

A mock LLM client that simulates inference responses for testing.
"""

from typing import Any, Dict, Optional
from unittest.mock import AsyncMock


class FakeInference:
    """
    Fake LLM inference client for testing.

    Simulates inference responses without calling external APIs.

    Usage:
        inference = FakeInference()
        result = await inference.complete("test query")
        assert result["success"] is True
    """

    def __init__(self, default_response: Optional[Dict[str, Any]] = None):
        self._responses: Dict[str, Dict[str, Any]] = {}
        self._call_count = 0
        self._calls: list[Dict[str, Any]] = []

        # Default response template
        self._default_response = default_response or {
            "success": True,
            "content": '{"skills": ["git"], "mission_brief": "Test", "confidence": 0.9, "reasoning": "Test"}',
            "model": "fake-model",
            "usage": {"tokens": 10},
        }

    def set_response(self, query: str, response: Dict[str, Any]) -> None:
        """Set a specific response for a query pattern."""
        self._responses[query] = response

    def clear_responses(self) -> None:
        """Clear all custom responses."""
        self._responses.clear()

    async def complete(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Complete a query with a simulated response.

        Tracks all calls for verification in tests.
        """
        self._call_count += 1
        call_info = {
            "query": query,
            "kwargs": kwargs,
            "timestamp": self._call_count,
        }
        self._calls.append(call_info)

        # Check for exact match first
        if query in self._responses:
            return self._responses[query]

        # Check for pattern match
        for pattern, response in self._responses.items():
            if pattern in query:
                return response

        return self._default_response

    async def stream(self, query: str, **kwargs):
        """Simulate streaming response (yields chunks)."""
        response = await self.complete(query, **kwargs)
        content = response.get("content", "")
        # Yield chunks of the content
        for i in range(0, len(content), 10):
            yield content[i : i + 10]

    @property
    def call_count(self) -> int:
        """Number of times complete was called."""
        return self._call_count

    @property
    def calls(self) -> list[Dict[str, Any]]:
        """List of all calls made (for verification)."""
        return list(self._calls)

    def reset(self) -> None:
        """Reset call count and calls."""
        self._call_count = 0
        self._calls.clear()


def create_mock_inference(response: Optional[Dict[str, Any]] = None) -> AsyncMock:
    """
    Create a mock inference client.

    Returns an AsyncMock with a configured complete method.

    Usage:
        mock_inference = create_mock_inference({"success": True, "content": "test"})
        result = await mock_inference.complete("query")
    """
    mock = AsyncMock()
    fake = FakeInference(default_response=response)
    mock.complete = fake.complete
    return mock
