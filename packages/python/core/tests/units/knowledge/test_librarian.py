"""
test_librarian.py - Librarian Unit Tests

Tests for the unified Librarian class with text and AST chunking.
"""

import tempfile

import pytest


class TestChunkMode:
    """Tests for the ChunkMode enum."""

    def test_chunk_mode_values(self):
        """ChunkMode should have expected values."""
        from omni.core.knowledge.librarian import ChunkMode

        assert ChunkMode.AUTO.value == "auto"
        assert ChunkMode.TEXT.value == "text"
        assert ChunkMode.AST.value == "ast"


class TestLibrarianInit:
    """Tests for Librarian initialization."""

    def test_librarian_init_with_defaults(self, tmp_path):
        """Librarian should have correct defaults."""
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(project_root=str(tmp_path))

        assert librarian.root == tmp_path.resolve()
        assert librarian.batch_size == 50
        assert librarian.chunk_mode.value == "auto"
        assert librarian.table_name == "knowledge_chunks"

    def test_librarian_init_custom_values(self, tmp_path):
        """Librarian should accept custom values."""
        from omni.core.knowledge.librarian import Librarian, ChunkMode

        librarian = Librarian(
            project_root=str(tmp_path),
            batch_size=100,
            chunk_mode=ChunkMode.AST,
            table_name="custom_table",
        )

        assert librarian.batch_size == 100
        assert librarian.chunk_mode == ChunkMode.AST
        assert librarian.table_name == "custom_table"


class TestLibrarianIngest:
    """Tests for Librarian ingestion."""

    def test_ingest_returns_dict(self, tmp_path):
        """ingest() should return a dictionary."""
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(project_root=str(tmp_path))
        result = librarian.ingest()

        assert isinstance(result, dict)
        assert "files_processed" in result
        assert "chunks_indexed" in result
        assert "errors" in result


class TestLibrarianGetStats:
    """Tests for Librarian get_stats."""

    def test_get_stats_returns_dict(self, tmp_path):
        """get_stats() should return a dictionary."""
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(project_root=str(tmp_path))
        stats = librarian.get_stats()

        assert isinstance(stats, dict)
        assert "table" in stats
        assert "record_count" in stats


class TestFileIngestor:
    """Tests for the FileIngestor class."""

    def test_discover_files_empty_dir(self, tmp_path):
        """discover_files should return empty list for empty directory."""
        from omni.core.knowledge.ingestion import FileIngestor

        ingestor = FileIngestor()
        files = ingestor.discover_files(tmp_path, use_knowledge_dirs=False)

        assert files == []

    def test_discover_files_finds_py_files(self, tmp_path):
        """discover_files should find Python files via git."""
        import subprocess

        from omni.core.knowledge.ingestion import FileIngestor

        # Create a Python file
        (tmp_path / "test.py").write_text("def hello():\n    return 'world'\n")

        # Initialize git repo (required for git discovery)
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)

        ingestor = FileIngestor()
        files = ingestor.discover_files(tmp_path, use_knowledge_dirs=False)

        assert len(files) == 1
        assert files[0].suffix == ".py"

    def test_create_records_empty(self, tmp_path):
        """create_records should return empty list for no files."""
        from omni.core.knowledge.ingestion import FileIngestor

        ingestor = FileIngestor()
        records = ingestor.create_records([], tmp_path)

        assert records == []

    def test_create_records_with_py_file(self, tmp_path):
        """create_records should create records from Python file."""
        import subprocess

        from omni.core.knowledge.ingestion import FileIngestor

        # Create a Python file
        py_file = tmp_path / "test.py"
        py_file.write_text("def hello():\n    return 'world'\n")

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)

        ingestor = FileIngestor()
        files = ingestor.discover_files(tmp_path, use_knowledge_dirs=False)
        records = ingestor.create_records(files, tmp_path)

        assert len(records) > 0
        assert records[0]["id"]

    def test_chunk_file_with_ast_mode(self, tmp_path):
        """_chunk_with_mode with AST mode should chunk Python files."""
        from omni.core.knowledge.ingestion import FileIngestor

        ingestor = FileIngestor()
        py_file = tmp_path / "test.py"
        py_file.write_text("def hello():\n    return 'world'\n")

        chunks = ingestor._chunk_with_mode(py_file, py_file.read_text(), "ast")

        assert len(chunks) > 0
        # AST chunking should find the function
        assert any("hello" in chunk["content"] for chunk in chunks)

    def test_chunk_file_with_text_mode(self, tmp_path):
        """_chunk_with_mode with TEXT mode should chunk any file."""
        from omni.core.knowledge.ingestion import FileIngestor

        ingestor = FileIngestor()
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("line1\nline2\nline3\nline4\nline5\n")

        chunks = ingestor._chunk_with_mode(txt_file, txt_file.read_text(), "text")

        assert len(chunks) > 0
        # Text chunking should preserve content
        combined = " ".join(chunk["content"] for chunk in chunks)
        assert "line1" in combined


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
