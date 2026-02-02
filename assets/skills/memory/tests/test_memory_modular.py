import pytest
from unittest.mock import AsyncMock, patch
from omni.test_kit.decorators import omni_skill


@pytest.mark.asyncio
@pytest.mark.timeout(30)
@omni_skill(name="memory")
class TestMemoryModular:
    """Modular tests for memory skill."""

    @pytest.fixture
    def mock_store(self):
        with patch("omni.foundation.services.vector.get_vector_store") as mock_get:
            store = AsyncMock()
            store.add = AsyncMock(return_value=True)
            store.search = AsyncMock(return_value=[])
            store.count = AsyncMock(return_value=42)
            store.create_index = AsyncMock(return_value=True)
            mock_get.return_value = store
            yield store

    async def test_save_memory(self, skill_tester, mock_store):
        """Test save_memory execution."""
        result = await skill_tester.run(
            "memory", "save_memory", content="Modular test memory", metadata={"source": "test"}
        )
        assert result.success
        assert "Saved memory" in result.output
        mock_store.add.assert_called_once()

    async def test_search_memory(self, skill_tester, mock_store):
        """Test search_memory execution."""
        mock_store.search.return_value = [
            AsyncMock(distance=0.1, content="Matched content", metadata={})
        ]

        result = await skill_tester.run("memory", "search_memory", query="search item")
        assert result.success
        assert "Found 1 matches" in result.output
        assert "Matched content" in result.output

    async def test_get_memory_stats(self, skill_tester, mock_store):
        """Test get_memory_stats execution."""
        result = await skill_tester.run("memory", "get_memory_stats")
        assert result.success
        assert "Stored memories: 42" in result.output

    async def test_index_memory(self, skill_tester, mock_store):
        """Test index_memory execution."""
        result = await skill_tester.run("memory", "index_memory")
        assert result.success
        assert "Search performance improved" in result.output
        mock_store.create_index.assert_called_once()
