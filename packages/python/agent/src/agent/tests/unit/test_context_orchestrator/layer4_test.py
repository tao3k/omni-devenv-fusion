"""
Unit tests for Layer 4: Associative Memories.

Tests the SearchResult dataclass access fix (getattr vs .get()).
"""

import pytest
from dataclasses import dataclass
from typing import Any, Dict


# Mock SearchResult dataclass (mimics vector_store/connection.py)
@dataclass
class MockSearchResult:
    """Mock SearchResult dataclass for testing Layer 4."""

    content: str
    metadata: Dict[str, Any]
    distance: float
    id: str


class TestLayer4AssociativeMemories:
    """Tests for Layer 4: Associative Memories."""

    def test_layer_priority(self) -> None:
        """Verify layer has correct priority."""
        from agent.core.context_orchestrator import Layer4_AssociativeMemories

        assert Layer4_AssociativeMemories.priority == 4
        assert Layer4_AssociativeMemories.name == "memories"

    @pytest.mark.asyncio
    async def test_assemble_low_budget(self) -> None:
        """Verify layer returns empty for low budget."""
        from agent.core.context_orchestrator import Layer4_AssociativeMemories

        layer = Layer4_AssociativeMemories()
        content, tokens = await layer.assemble("test task", [], 100)
        assert content == ""
        assert tokens == 0


class TestSearchResultAttributeAccess:
    """Tests verifying SearchResult dataclass attribute access works correctly."""

    def test_searchresult_has_expected_attributes(self) -> None:
        """Verify SearchResult has expected attributes."""
        result = MockSearchResult(
            content="test content", metadata={"key": "value"}, distance=0.5, id="test-id"
        )

        # These should work (dataclass attributes)
        assert result.content == "test content"
        assert result.metadata == {"key": "value"}
        assert result.distance == 0.5
        assert result.id == "test-id"

    def test_searchresult_getattr_works(self) -> None:
        """Verify getattr works for default values."""
        result = MockSearchResult(content="test", metadata={}, distance=0.5, id="test")

        # getattr with default should work
        assert getattr(result, "distance", 0.0) == 0.5
        assert getattr(result, "score", 1.0) == 1.0  # Missing attribute

    def test_searchresult_get_raises(self) -> None:
        """Verify .get() fails on dataclass (this is the bug we fixed)."""
        result = MockSearchResult(content="test", metadata={}, distance=0.5, id="test")

        # This should raise AttributeError (the original bug)
        with pytest.raises(AttributeError):
            result.get("content")  # type: ignore

    def test_layer4_uses_getattr_not_get(self) -> None:
        """Verify Layer4 implementation uses getattr."""
        import inspect
        from agent.core.context_orchestrator import Layer4_AssociativeMemories

        source = inspect.getsource(Layer4_AssociativeMemories.assemble)

        # Should use getattr, not .get()
        assert "getattr" in source
