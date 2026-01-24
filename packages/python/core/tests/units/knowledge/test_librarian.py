"""
test_librarian.py - Librarian Tests

Tests for the Librarian knowledge management class.
"""

import os
import tempfile

import pytest


class TestKnowledgeEntry:
    """Tests for the KnowledgeEntry dataclass."""

    def test_knowledge_entry_creation(self):
        """KnowledgeEntry should store all fields."""
        from omni.core.knowledge.librarian import KnowledgeEntry

        entry = KnowledgeEntry(
            id="test_001",
            content="test content",
            source="test.md",
            metadata={"key": "value"},
            score=0.85,
        )
        assert entry.id == "test_001"
        assert entry.content == "test content"
        assert entry.source == "test.md"
        assert entry.metadata == {"key": "value"}
        assert entry.score == 0.85


class TestSearchResult:
    """Tests for the SearchResult dataclass."""

    def test_search_result_creation(self):
        """SearchResult should store entry and score."""
        from omni.core.knowledge.librarian import KnowledgeEntry, SearchResult

        entry = KnowledgeEntry(id="test_001", content="content", source="test.md", metadata={})
        result = SearchResult(entry=entry, score=0.9)
        assert result.entry.id == "test_001"
        assert result.score == 0.9


class TestLibrarian:
    """Tests for the Librarian class."""

    def test_librarian_init_defaults(self):
        """Librarian should have correct defaults."""
        from omni.core.knowledge.librarian import Librarian

        # Create with mocked store to avoid initialization issues
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_path = f.name

        try:
            # Mock the bridge import to prevent actual initialization
            import unittest.mock as mock

            with mock.patch.dict("sys.modules", {"omni.foundation.bridge": None}):
                librarian = Librarian(temp_path, dimension=1536)
                assert librarian._dimension == 1536
                assert librarian._collection == "knowledge"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_ingest_file_not_found(self):
        """ingest_file should return False for non-existent file."""
        import unittest.mock as mock

        from omni.core.knowledge.librarian import Librarian

        with mock.patch.dict("sys.modules", {"omni.foundation.bridge": None}):
            librarian = Librarian()
            librarian._initialized = False  # Ensure not ready

            result = librarian.ingest_file("/nonexistent/file.md")
            assert result is False

    def test_ingest_file_success(self):
        """ingest_file should return True and cache entries."""
        import unittest.mock as mock

        from omni.core.knowledge.librarian import Librarian

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test Document\n\nSome content here.")
            temp_path = f.name

        try:
            with mock.patch.dict("sys.modules", {"omni.foundation.bridge": None}):
                librarian = Librarian()
                librarian._initialized = False  # Skip store init

                result = librarian.ingest_file(temp_path)
                assert result is True
                assert hasattr(librarian, "_cache")
                assert len(librarian._cache) > 0
        finally:
            os.unlink(temp_path)

    def test_ingest_file_with_metadata(self):
        """ingest_file should use provided metadata."""
        import unittest.mock as mock

        from omni.core.knowledge.librarian import Librarian

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content")
            temp_path = f.name

        try:
            with mock.patch.dict("sys.modules", {"omni.foundation.bridge": None}):
                librarian = Librarian()
                librarian._initialized = False

                metadata = {"author": "test", "version": "1.0"}
                result = librarian.ingest_file(temp_path, metadata=metadata)
                assert result is True
                entry = librarian._cache[0]
                assert entry.metadata.get("author") == "test"
                assert entry.metadata.get("source") == temp_path
        finally:
            os.unlink(temp_path)

    def test_ingest_directory_not_found(self):
        """ingest_directory should return 0 for non-existent directory."""
        import unittest.mock as mock

        from omni.core.knowledge.librarian import Librarian

        with mock.patch.dict("sys.modules", {"omni.foundation.bridge": None}):
            librarian = Librarian()
            librarian._initialized = False

            result = librarian.ingest_directory("/nonexistent/dir")
            assert result == 0

    def test_ingest_directory_success(self):
        """ingest_directory should return count of ingested files."""
        import unittest.mock as mock

        from omni.core.knowledge.librarian import Librarian

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            for i in range(3):
                with open(os.path.join(tmpdir, f"file{i}.md"), "w") as f:
                    f.write(f"# File {i}\nContent here.")

            with mock.patch.dict("sys.modules", {"omni.foundation.bridge": None}):
                librarian = Librarian()
                librarian._initialized = False

                result = librarian.ingest_directory(tmpdir, extensions=[".md"])
                assert result == 3

    def test_ingest_directory_filters_by_extension(self):
        """ingest_directory should filter by extension."""
        import unittest.mock as mock

        from omni.core.knowledge.librarian import Librarian

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with different extensions
            with open(os.path.join(tmpdir, "file.md"), "w") as f:
                f.write("MD content")
            with open(os.path.join(tmpdir, "file.txt"), "w") as f:
                f.write("TXT content")
            with open(os.path.join(tmpdir, "file.py"), "w") as f:
                f.write("# Python")

            with mock.patch.dict("sys.modules", {"omni.foundation.bridge": None}):
                librarian = Librarian()
                librarian._initialized = False

                # Only .md files
                result = librarian.ingest_directory(tmpdir, extensions=[".md"])
                assert result == 1

    @pytest.mark.asyncio
    async def test_search_not_ready(self):
        """search() should return empty list when not ready."""
        import unittest.mock as mock

        from omni.core.knowledge.librarian import Librarian

        with mock.patch.dict("sys.modules", {"omni.foundation.bridge": None}):
            librarian = Librarian()
            librarian._initialized = False

            result = await librarian.search("test query")
            assert result == []

    def test_get_stats_not_ready(self):
        """get_stats() should return ready: False when not initialized."""
        import unittest.mock as mock

        from omni.core.knowledge.librarian import Librarian

        with mock.patch.dict("sys.modules", {"omni.foundation.bridge": None}):
            librarian = Librarian()
            librarian._initialized = False

            stats = librarian.get_stats()
            assert stats["ready"] is False


class TestLibrarianChunking:
    """Tests for the Librarian text chunking functionality."""

    def test_chunk_text_small(self):
        """Small text should not be chunked."""
        import unittest.mock as mock

        from omni.core.knowledge.librarian import Librarian

        with mock.patch.dict("sys.modules", {"omni.foundation.bridge": None}):
            librarian = Librarian()
            text = "Short text"
            chunks = librarian._chunk_text(text, max_chunk_size=2000)
            assert len(chunks) == 1
            assert chunks[0] == "Short text"

    def test_chunk_text_large(self):
        """Large text should be split into chunks."""
        import unittest.mock as mock

        from omni.core.knowledge.librarian import Librarian

        with mock.patch.dict("sys.modules", {"omni.foundation.bridge": None}):
            librarian = Librarian()
            # Create text larger than chunk size - each line is ~8 chars
            # Need >2000 chars total to trigger chunking
            text = "line1234\n" * 500  # ~500 * 9 = 4500 chars
            chunks = librarian._chunk_text(text, max_chunk_size=2000)
            assert len(chunks) > 1

    def test_chunk_text_preserves_lines(self):
        """Chunked text should preserve line boundaries."""
        import unittest.mock as mock

        from omni.core.knowledge.librarian import Librarian

        with mock.patch.dict("sys.modules", {"omni.foundation.bridge": None}):
            librarian = Librarian()
            lines = ["line1", "line2", "line3", "line4", "line5"]
            text = "\n".join(lines)
            chunks = librarian._chunk_text(text, max_chunk_size=2000)

            # All lines should be in some chunk
            chunked_text = "\n".join(chunks)
            for line in lines:
                assert line in chunked_text


class TestHyperSearch:
    """Tests for the HyperSearch class."""

    @pytest.mark.asyncio
    async def test_search_with_highlighting(self):
        """search_with_highlighting should return highlighted results."""
        import unittest.mock as mock

        from omni.core.knowledge.librarian import (
            HyperSearch,
            KnowledgeEntry,
            Librarian,
            SearchResult,
        )

        with mock.patch.dict("sys.modules", {"omni.foundation.bridge": None}):
            librarian = Librarian()
            librarian._initialized = False

            # Add test entry to cache directly
            librarian._cache = [
                KnowledgeEntry(
                    id="test_001",
                    content="This is test content about testing",
                    source="test.md",
                    metadata={},
                )
            ]

            hyper = HyperSearch(librarian)
            with mock.patch.object(
                hyper._librarian, "search", new_callable=mock.AsyncMock
            ) as mock_search:
                mock_entry = KnowledgeEntry(
                    id="test_001",
                    content="This is test content about testing",
                    source="test.md",
                    metadata={},
                )
                mock_search.return_value = [SearchResult(entry=mock_entry, score=0.9)]

                results = await hyper.search_with_highlighting("test")

                assert len(results) == 1
                assert "content_preview" in results[0]
                assert results[0]["id"] == "test_001"

    @pytest.mark.asyncio
    async def test_find_related(self):
        """find_related should search for related entries."""
        import unittest.mock as mock

        from omni.core.knowledge.librarian import (
            HyperSearch,
            KnowledgeEntry,
            Librarian,
            SearchResult,
        )

        with mock.patch.dict("sys.modules", {"omni.foundation.bridge": None}):
            librarian = Librarian()
            librarian._initialized = False

            hyper = HyperSearch(librarian)

            with mock.patch.object(
                hyper._librarian, "search", new_callable=mock.AsyncMock
            ) as mock_search:
                mock_entry = KnowledgeEntry(
                    id="test_001", content="This is test content", source="test.md", metadata={}
                )
                mock_search.return_value = [SearchResult(entry=mock_entry, score=0.9)]

                results = await hyper.find_related("test_001")

                assert len(results) == 1
