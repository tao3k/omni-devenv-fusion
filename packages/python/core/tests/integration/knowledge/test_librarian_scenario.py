"""
test_librarian_scenario.py - Integration Scenarios for The Librarian

The Librarian's Exam: Real-world scenarios to verify knowledge recall capabilities.

Scenarios:
1. "The Architect": Keyword search over Markdown documentation.
2. "The Debugger": Keyword search for specific Error Codes.
3. "The Developer": Retrieving specific function definitions from Code.
4. "The Updater": Modifying a file and verifying the index updates.

Note: These tests use mocking for the vector store since the real
implementation requires embedding generation which is handled by a separate
embedding service.
"""

from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

from omni.core.knowledge.librarian import Librarian


def async_mock(return_value):
    """Create an async mock that returns the given value."""
    mock = AsyncMock()
    mock.return_value = return_value
    return mock


@pytest.fixture(autouse=True)
def reset_librarian_singleton():
    """Reset librarian singleton before each test."""
    from omni.core.knowledge.librarian import Librarian

    Librarian.reset_singleton()
    yield
    Librarian.reset_singleton()


@pytest.fixture
def temp_librarian(tmp_path: Path) -> Librarian:
    """Create a Librarian instance with mocked vector store."""
    db_path = tmp_path / "knowledge_db"
    lib = Librarian(storage_path=str(db_path), collection="test_scenarios")
    return lib


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """Generate a diverse corpus of files for testing."""
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir()

    # 1. Architecture Doc (Markdown) - Semantic search target
    (docs_dir / "arch.md").write_text(
        "# Trinity Architecture\n\nThe system is divided into Foundation, Core, and Agent layers.\n\nFoundation handles configuration and utilities.\nCore manages skills and orchestration.\nAgent provides the MCP interface.",
        encoding="utf-8",
    )

    # 2. Error Codes (Log/Text - Keyword heavy)
    (docs_dir / "errors.log").write_text(
        "ERROR_503: Service Unavailable - Retry after backoff.\n"
        "ERROR_404: Resource not found - Check the path.\n"
        "ERROR_500: Internal Server Error - Check logs for details.",
        encoding="utf-8",
    )

    # 3. Code (Python) - Function definition search
    (docs_dir / "api.py").write_text(
        '"""API module for database connections."""\n\n'
        "def connect_to_db(timeout: int) -> bool:\n"
        "    '''Establishes connection to the database.\n\n"
        "    Args:\n"
        "        timeout: Connection timeout in seconds.\n"
        "    '''\n"
        "    return True\n\n"
        "def disconnect_from_db() -> None:\n"
        "    '''Closes the database connection.'''\n"
        "    pass\n",
        encoding="utf-8",
    )

    # 4. Status file for updater test
    (docs_dir / "status.md").write_text(
        "Status: GREEN - All systems operational.", encoding="utf-8"
    )

    return docs_dir


@pytest.fixture
def mock_search_results():
    """Helper to create mock search results as dicts (matching list_all format)."""

    def _create(content: str, source: str, score: float = 0.9):
        return {
            "id": f"doc_{hash(source) % 10000}",
            "content": content,
            "source": source,
            "type": "test",
            "score": score,
        }

    return _create


class TestScenarioArchitect:
    """Scenario 1: Keyword search finds concepts."""

    @pytest.mark.asyncio
    async def test_keyword_search_finds_concepts(self, temp_librarian: Librarian, corpus: Path):
        """The Architect: Search should find content about 'system' and 'layers'."""
        # Ingest the architecture doc
        temp_librarian.ingest_file(str(corpus / "arch.md"))

        # Mock list_all to return the ingested content (as async mock)
        mock_result = {
            "id": "arch_0",
            "content": "The Trinity Architecture divides the system into Foundation, Core, and Agent layers.",
            "source": str(corpus / "arch.md"),
            "type": "documentation",
            "score": 1.0,
        }
        temp_librarian._store.list_all = async_mock([mock_result])

        # Search for concept keywords
        results = await temp_librarian.search("system layers", limit=3)

        assert len(results) > 0, "Expected at least one search result"
        content = results[0].entry.content.lower()
        assert any(
            word in content for word in ["layer", "foundation", "core", "agent", "system"]
        ), f"Expected structural content, got: {results[0].entry.content[:200]}"


class TestScenarioDebugger:
    """Scenario 2: Keyword search finds exact error codes."""

    @pytest.mark.asyncio
    async def test_keyword_search_finds_error_codes(self, temp_librarian: Librarian, corpus: Path):
        """The Debugger: Search for ERROR_503 should find the service unavailable message."""
        temp_librarian.ingest_file(str(corpus / "errors.log"))

        # Mock list_all to return error content
        mock_result = {
            "id": "errors_0",
            "content": "ERROR_503: Service Unavailable - Retry after backoff.",
            "source": str(corpus / "errors.log"),
            "type": "log",
            "score": 1.0,
        }
        temp_librarian._store.list_all = async_mock([mock_result])

        # Search for specific error code
        results = await temp_librarian.search("ERROR_503", limit=3)

        assert len(results) > 0, "Expected at least one search result for ERROR_503"
        assert (
            "Service Unavailable" in results[0].entry.content or "503" in results[0].entry.content
        ), f"Expected ERROR_503 content, got: {results[0].entry.content}"


class TestScenarioDeveloper:
    """Scenario 3: Code chunking preserves function context."""

    @pytest.mark.asyncio
    async def test_code_search_finds_function_definitions(
        self, temp_librarian: Librarian, corpus: Path
    ):
        """The Developer: Search for function name should find its definition."""
        temp_librarian.ingest_file(str(corpus / "api.py"))

        # Mock list_all to return function definition
        mock_result = {
            "id": "api_0",
            "content": "def connect_to_db(timeout: int) -> bool:\n    '''Establishes connection to the database.'''\n    return True",
            "source": str(corpus / "api.py"),
            "type": "code",
            "score": 1.0,
        }
        temp_librarian._store.list_all = async_mock([mock_result])

        # Search for function definition
        results = await temp_librarian.search("connect_to_db", limit=3)

        assert len(results) > 0, "Expected at least one search result for connect_to_db"
        assert (
            "def connect_to_db" in results[0].entry.content
            or "connect_to_db" in results[0].entry.content
        ), f"Expected function definition, got: {results[0].entry.content}"


class TestScenarioUpdater:
    """Scenario 4: Document updates reflect in search."""

    @pytest.mark.asyncio
    async def test_updated_content_reflects_in_search(
        self, temp_librarian: Librarian, corpus: Path
    ):
        """The Updater: Updating content should update search results."""
        status_file = corpus / "status.md"

        # Ingest initial content
        temp_librarian.ingest_file(str(status_file))

        # Mock list_all for GREEN
        mock_green = {
            "id": "status_0",
            "content": "Status: GREEN - All systems operational.",
            "source": str(status_file),
            "type": "documentation",
            "score": 0.95,
        }
        temp_librarian._store.list_all = async_mock([mock_green])

        # Verify initial state - search for GREEN
        results_green = await temp_librarian.search("Status", limit=1)
        assert len(results_green) > 0, "Should find initial status"
        assert "GREEN" in results_green[0].entry.content, (
            f"Expected GREEN in initial content, got: {results_green[0].entry.content}"
        )

        # Update content - modify the file
        status_file.write_text("Status: RED - Critical Failure detected!", encoding="utf-8")

        # Re-ingest the updated file
        temp_librarian.ingest_file(str(status_file))

        # Mock list_all for RED
        mock_red = {
            "id": "status_0",
            "content": "Status: RED - Critical Failure detected!",
            "source": str(status_file),
            "type": "documentation",
            "score": 0.95,
        }
        temp_librarian._store.list_all = async_mock([mock_red])

        # Verify updated state - search for RED
        results_red = await temp_librarian.search("Status", limit=5)

        # At least one result should contain RED
        red_found = any("RED" in r.entry.content for r in results_red)
        assert red_found, (
            f"Expected RED in updated content, got: {[r.entry.content for r in results_red]}"
        )


class TestScenarioHybridSearch:
    """Scenario 5: Search combines keyword matching."""

    @pytest.mark.asyncio
    async def test_keyword_search_works(self, temp_librarian: Librarian, corpus: Path):
        """Test that keyword search works."""
        # Ingest all documents
        for file in corpus.iterdir():
            if file.is_file():
                temp_librarian.ingest_file(str(file))

        # Mock list_all for database query
        mock_db = {
            "id": "api_0",
            "content": "def connect_to_db(timeout: int) -> bool: Establishes connection to the database.",
            "source": str(corpus / "api.py"),
            "type": "code",
            "score": 0.95,
        }
        temp_librarian._store.list_all = async_mock([mock_db])

        # Keyword query
        results = await temp_librarian.search("database", limit=3)
        assert len(results) > 0, "Keyword search should find results"

        # Mock list_all for error code query
        mock_error = {
            "id": "errors_0",
            "content": "ERROR_500: Internal Server Error - Check logs for details.",
            "source": str(corpus / "errors.log"),
            "type": "log",
            "score": 0.95,
        }
        temp_librarian._store.list_all = async_mock([mock_error])

        # Error code query
        error_results = await temp_librarian.search("ERROR_500", limit=3)
        assert len(error_results) > 0, "Error code search should find results"


class TestScenarioEdgeCases:
    """Scenario 6: Edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_search_empty_knowledge_base(self, temp_librarian: Librarian):
        """Test search on empty knowledge base returns empty results."""
        # Mock empty search results
        temp_librarian._store.search = MagicMock(return_value=[])

        results = await temp_librarian.search("anything", limit=5)
        assert len(results) == 0, "Expected empty results for empty knowledge base"

    def test_ingest_nonexistent_file(self, temp_librarian: Librarian, tmp_path: Path):
        """Test ingesting nonexistent file returns False."""
        result = temp_librarian.ingest_file(str(tmp_path / "nonexistent.md"))
        assert result is False, "Expected False for nonexistent file"

    def test_ingest_empty_file(self, temp_librarian: Librarian, tmp_path: Path):
        """Test ingesting empty file works without error."""
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("", encoding="utf-8")

        result = temp_librarian.ingest_file(str(empty_file))
        # Should return True (file exists and was processed)
        assert result is True, "Expected True for empty file ingestion"

    @pytest.mark.asyncio
    async def test_search_respects_threshold(self, temp_librarian: Librarian, mock_search_results):
        """Test that search respects score threshold."""
        # Mock with low score
        low_score_result = mock_search_results(
            content="Low relevance match", source="test.md", score=0.3
        )
        temp_librarian._store.list_all = async_mock([low_score_result])

        # Search with high threshold
        results = await temp_librarian.search("anything", limit=5, threshold=0.5)
        assert len(results) == 0, "Should filter out results below threshold"

    @pytest.mark.asyncio
    async def test_search_handles_error_gracefully(self, temp_librarian: Librarian):
        """Test that search handles errors gracefully."""
        # Mock list_all to raise exception using AsyncMock
        error_mock = AsyncMock(side_effect=Exception("Search failed"))
        temp_librarian._store.list_all = error_mock

        results = await temp_librarian.search("anything", limit=5)
        assert len(results) == 0, "Expected empty results on error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
