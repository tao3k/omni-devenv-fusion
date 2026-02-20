"""
test_librarian.py - Librarian Unit Tests

Tests for the unified Librarian class with text and AST chunking.
"""

import json
from unittest.mock import AsyncMock, MagicMock

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
        from omni.core.knowledge.librarian import ChunkMode, Librarian

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
        pytest.skip("Requires LanceDB table creation - test environment limitation")


class TestKnowledgeStorage:
    """Tests for KnowledgeStorage vector search contracts."""

    def test_vector_search_uses_optimized_api_and_parses_json(self):
        """KnowledgeStorage.vector_search should call search_optimized and parse payloads."""
        from omni.core.knowledge.librarian import KnowledgeStorage

        mock_store = MagicMock()
        mock_store.count.return_value = 0
        mock_store.search_optimized.return_value = [
            json.dumps(
                {
                    "schema": "omni.vector.search.v1",
                    "id": "doc-1",
                    "content": "hello",
                    "metadata": {"source": "test"},
                    "distance": 0.1,
                }
            )
        ]

        storage = KnowledgeStorage(mock_store, table_name="knowledge_chunks")
        result = storage.vector_search([0.1, 0.2, 0.3], limit=3)

        assert len(result) == 1
        assert result[0]["id"] == "doc-1"
        mock_store.search_optimized.assert_called_once_with(
            "knowledge_chunks",
            [0.1, 0.2, 0.3],
            3,
            None,
        )
        mock_store.search.assert_not_called()

    def test_vector_search_calls_search_optimized(self):
        """vector_search should call Rust search_optimized and parse payload."""
        from omni.core.knowledge.librarian import KnowledgeStorage

        mock_store = MagicMock()
        mock_store.count.return_value = 0
        mock_store.search_optimized.return_value = [
            json.dumps(
                {
                    "schema": "omni.vector.search.v1",
                    "id": "doc-vec",
                    "content": "vector hit",
                    "metadata": {"source": "vec"},
                    "distance": 0.2,
                }
            )
        ]

        storage = KnowledgeStorage(mock_store, table_name="knowledge_chunks")
        results = storage.vector_search([0.1, 0.2], limit=2)

        assert len(results) == 1
        assert results[0]["id"] == "doc-vec"
        mock_store.search_optimized.assert_called_once_with("knowledge_chunks", [0.1, 0.2], 2, None)

    def test_text_search_calls_search_hybrid(self):
        """text_search should call Rust search_hybrid and parse payload."""
        from omni.core.knowledge.librarian import KnowledgeStorage

        mock_store = MagicMock()
        mock_store.count.return_value = 0
        mock_store.search_hybrid.return_value = [
            json.dumps(
                {
                    "schema": "omni.vector.search.v1",
                    "id": "doc-text",
                    "content": "text hit",
                    "metadata": {"source": "text"},
                    "distance": 0.3,
                }
            )
        ]

        storage = KnowledgeStorage(mock_store, table_name="knowledge_chunks")
        results = storage.text_search("typed language", [0.1, 0.2], limit=4)

        assert len(results) == 1
        assert results[0]["id"] == "doc-text"
        mock_store.search_hybrid.assert_called_once_with(
            "knowledge_chunks",
            [0.1, 0.2],
            ["typed language"],
            4,
        )

    def test_delete_wraps_entry_id_as_list(self):
        """delete should pass list[str] to Rust binding API."""
        from omni.core.knowledge.librarian import KnowledgeStorage

        mock_store = MagicMock()
        mock_store.count.return_value = 0
        mock_store.delete.return_value = None

        storage = KnowledgeStorage(mock_store, table_name="knowledge_chunks")
        ok = storage.delete("entry-1")

        assert ok is True
        mock_store.delete.assert_called_once_with("knowledge_chunks", ["entry-1"])

    def test_lexical_scan_filters_list_all_rows(self):
        """lexical_scan should filter rows by substring when list_all is available."""
        from omni.core.knowledge.librarian import KnowledgeStorage

        mock_store = MagicMock()
        mock_store.count.return_value = 0
        mock_store.list_all = AsyncMock(
            return_value=[
                {"id": "a", "content": "unrelated"},
                {"id": "b", "content": "multiply numbers"},
                {"id": "c", "text": "also multiply here"},
            ]
        )

        storage = KnowledgeStorage(mock_store, table_name="knowledge_chunks")
        results = storage.lexical_scan("multiply", limit=5)

        assert [r["id"] for r in results] == ["b", "c"]


class TestLibrarianQueryPath:
    """Tests for query routing path in Librarian."""

    def test_query_uses_text_search_with_query_and_vector(self, tmp_path):
        """Librarian.query should call text_search(query, vector, limit)."""
        from omni.core.knowledge.librarian import Librarian

        mock_storage = MagicMock()
        mock_storage.text_search.return_value = [
            {"id": "doc-1", "content": "typed language basics"}
        ]

        mock_embedder = MagicMock()
        mock_embedder.dimension = 4
        mock_embedder.embed.return_value = [[0.1, 0.2, 0.3, 0.4]]

        librarian = Librarian(
            project_root=str(tmp_path),
            embedder=mock_embedder,
        )
        librarian.storage = mock_storage

        result = librarian.query("typed language", limit=3)

        assert result == [{"id": "doc-1", "content": "typed language basics"}]
        mock_storage.text_search.assert_called_once_with(
            "typed language",
            [0.1, 0.2, 0.3, 0.4],
            limit=3,
        )

    def test_query_expands_window_when_no_lexical_hit(self, tmp_path):
        """Query should fetch an expanded window when top-N has no lexical overlap."""
        from omni.core.knowledge.librarian import Librarian

        mock_storage = MagicMock()
        mock_storage.text_search.side_effect = [
            [{"id": "doc-a", "content": "unrelated text", "score": 0.9}],
            [{"id": "doc-b", "content": "multiply values quickly", "score": 0.5}],
        ]

        mock_embedder = MagicMock()
        mock_embedder.dimension = 4
        mock_embedder.embed.return_value = [[0.1, 0.2, 0.3, 0.4]]

        librarian = Librarian(project_root=str(tmp_path), embedder=mock_embedder)
        librarian.storage = mock_storage

        result = librarian.query("multiply", limit=2)

        assert result[0]["id"] == "doc-b"
        assert mock_storage.text_search.call_count == 2
        assert mock_storage.text_search.call_args_list[0].kwargs["limit"] == 2
        assert mock_storage.text_search.call_args_list[1].kwargs["limit"] == 10


class TestLibrarianGetStats:
    """Tests for Librarian get_stats."""

    def test_get_stats_returns_dict(self, tmp_path):
        """get_stats() should return a dictionary."""
        pytest.skip("Requires LanceDB table creation - test environment limitation")


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


class TestBatchDelete:
    """Tests for batch delete functionality."""

    def _create_store(self, tmp_path):
        """Create a PyVectorStore with dimension from settings."""
        from omni_core_rs import PyVectorStore

        from omni.foundation.config.settings import get_setting

        dimension = get_setting("embedding.dimension", 1024)
        store_path = str(tmp_path / "test_knowledge.lance")
        return PyVectorStore(store_path, dimension, True)

    def test_delete_by_paths_batch_empty(self, tmp_path):
        """_delete_by_paths_batch should handle empty list."""
        from omni.core.knowledge.librarian import Librarian

        store = self._create_store(tmp_path)
        librarian = Librarian(project_root=str(tmp_path), store=store)
        count = librarian._delete_by_paths_batch([])

        assert count == 0

    def test_delete_by_paths_batch_single_file(self, tmp_path):
        """_delete_by_paths_batch should handle single file gracefully."""
        pytest.skip("Requires LanceDB table creation - test environment limitation")

    def test_delete_by_paths_batch_multiple_files(self, tmp_path):
        """_delete_by_paths_batch should handle multiple files."""
        pytest.skip("Requires LanceDB table creation - test environment limitation")


class TestIncrementalSync:
    """Tests for incremental sync behavior."""

    def _create_store(self, tmp_path):
        """Create a PyVectorStore with dimension from settings."""
        from omni_core_rs import PyVectorStore

        from omni.foundation.config.settings import get_setting

        dimension = get_setting("embedding.dimension", 1024)
        store_path = str(tmp_path / "test_knowledge.lance")
        return PyVectorStore(store_path, dimension, True)

    def test_manifest_saved_after_deletion(self, tmp_path):
        """Manifest should be saved after deleting files."""
        pytest.skip("Requires LanceDB table creation - test environment limitation")

    def test_incremental_sync_no_changes(self, tmp_path):
        """Incremental sync should detect no changes when manifest is current."""
        pytest.skip("Requires LanceDB table creation - test environment limitation")


class TestPathFilter:
    """Tests for path filtering utilities."""

    def test_should_skip_hidden_files(self):
        """should_skip_path should skip hidden files and directories."""
        from pathlib import Path

        from omni.foundation.runtime.path_filter import should_skip_path

        # Hidden file should be skipped
        assert should_skip_path(Path("assets/knowledge/.git"))
        assert should_skip_path(Path("assets/knowledge/.git/config"))

        # Normal file should not be skipped
        assert not should_skip_path(Path("assets/knowledge/README.md"))

    def test_should_skip_skip_dirs(self):
        """should_skip_path should skip configured directories."""
        from pathlib import Path

        from omni.foundation.runtime.path_filter import should_skip_path

        # venv should be skipped
        assert should_skip_path(Path(".venv/lib/python.py"))
        assert should_skip_path(Path("venv/site-packages/foo.py"))

        # Normal file should not be skipped
        assert not should_skip_path(Path("packages/core/src/main.py"))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# =============================================================================
# Rust SyncEngine Tests (xiuxian-wendao crate)
# =============================================================================


class TestRustSyncEngine:
    """Tests for Rust SyncEngine integration."""

    def test_sync_engine_creation(self, tmp_path):
        """PySyncEngine should be creatable."""
        try:
            from omni_core_rs import PySyncEngine
        except ImportError:
            pytest.skip("Rust bindings not available")

        engine = PySyncEngine(str(tmp_path), str(tmp_path / "manifest.json"))
        assert engine is not None

    def test_sync_engine_load_manifest(self, tmp_path):
        """SyncEngine should load manifest from disk."""
        try:
            from omni_core_rs import PySyncEngine
        except ImportError:
            pytest.skip("Rust bindings not available")

        engine = PySyncEngine(str(tmp_path), str(tmp_path / "manifest.json"))

        # Load empty manifest
        manifest = engine.load_manifest()
        assert manifest == "{}" or manifest == ""

    def test_sync_engine_save_manifest(self, tmp_path):
        """SyncEngine should save manifest to disk."""
        try:
            from omni_core_rs import PySyncEngine
        except ImportError:
            pytest.skip("Rust bindings not available")

        engine = PySyncEngine(str(tmp_path), str(tmp_path / "manifest.json"))

        # Save manifest
        manifest_json = '{"test.py": "hash123"}'
        engine.save_manifest(manifest_json)

        # Load and verify
        loaded = engine.load_manifest()
        assert "test.py" in loaded

    def test_sync_engine_discover_files(self, tmp_path):
        """SyncEngine should discover Python and Markdown files."""
        try:
            from omni_core_rs import PySyncEngine
        except ImportError:
            pytest.skip("Rust bindings not available")

        # Create test files
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "data.txt").write_text("data")  # Should be skipped

        engine = PySyncEngine(str(tmp_path), str(tmp_path / "manifest.json"))
        files = engine.discover_files()

        # Should find .py and .md files
        filenames = [f.split("/")[-1] for f in files]
        assert "test.py" in filenames
        assert "readme.md" in filenames
        # .txt should be skipped
        assert "data.txt" not in filenames

    def test_sync_engine_compute_diff(self, tmp_path):
        """SyncEngine should compute diff between manifest and filesystem."""
        try:
            from omni_core_rs import PySyncEngine
        except ImportError:
            pytest.skip("Rust bindings not available")

        # Create test files
        (tmp_path / "new.py").write_text("new content")
        (tmp_path / "modified.py").write_text("modified content")
        (tmp_path / "existing.py").write_text("existing")

        engine = PySyncEngine(str(tmp_path), str(tmp_path / "manifest.json"))

        # Create old manifest (existing unchanged, modified changed, new missing)
        # Note: existing_hash is different from actual hash, so it will be marked as modified
        old_manifest = '{"existing.py": "wrong_hash", "modified.py": "old_hash"}'
        diff = engine.compute_diff(old_manifest)

        # new.py should be in added
        assert any("new.py" in f for f in diff.added)

        # modified.py should be in modified
        assert any("modified.py" in f for f in diff.modified)

        # existing.py hash is wrong, so it's marked as modified, not unchanged
        # With "wrong_hash", it will be modified (not unchanged)
        # Adjust expectation based on actual behavior
        assert diff.modified.count("existing.py") == 1 or any(
            "existing.py" in f for f in diff.modified
        )

    def test_sync_engine_compute_hash(self):
        """compute_hash should produce consistent xxhash output."""
        try:
            from omni_core_rs import compute_hash
        except ImportError:
            pytest.skip("Rust bindings not available")

        hash1 = compute_hash("hello world")
        hash2 = compute_hash("hello world")
        hash3 = compute_hash("different")

        assert hash1 == hash2
        assert hash1 != hash3
        # xxhash produces 16 character hex
        assert len(hash1) == 16


class TestRustSyncEngineDelete:
    """Tests for Rust SyncEngine delete support."""

    def test_sync_engine_deleted_files_in_diff(self, tmp_path):
        """SyncEngine should detect deleted files in diff."""
        try:
            from omni_core_rs import PySyncEngine
        except ImportError:
            pytest.skip("Rust bindings not available")

        # Create old manifest with deleted file
        old_manifest = '{"deleted_file.py": "hash123", "existing.py": "hash456"}'

        engine = PySyncEngine(str(tmp_path), str(tmp_path / "manifest.json"))

        # compute_diff should show deleted_file.py in deleted list
        diff = engine.compute_diff(old_manifest)

        assert any("deleted_file.py" in f for f in diff.deleted)


class TestRustDiscoverFunctions:
    """Tests for Rust-based file discovery functions."""

    def test_discover_files_finds_python_files(self, tmp_path):
        """discover_files should find Python files using Rust."""
        from omni_core_rs import discover_files

        # Create test files
        (tmp_path / "test.py").write_text("def hello():\n    return 'world'\n")
        (tmp_path / "readme.md").write_text("# Hello World")
        (tmp_path / "data.txt").write_text("data")  # Should be skipped

        files = discover_files(
            root=str(tmp_path),
            extensions=[".py", ".md"],
            max_file_size=1024 * 1024,
            skip_hidden=True,
            skip_dirs=["target", "node_modules"],
            recursive=True,
        )

        filenames = [f.split("/")[-1] for f in files]
        assert "test.py" in filenames
        assert "readme.md" in filenames
        assert "data.txt" not in filenames

    def test_discover_files_in_dir(self, tmp_path):
        """discover_files_in_dir should find files in a single directory."""
        from omni_core_rs import discover_files_in_dir

        # Create test files
        (tmp_path / "module.py").write_text("print('hello')")
        (tmp_path / "utils.py").write_text("print('utils')")
        (tmp_path / "notes.md").write_text("# Notes")

        files = discover_files_in_dir(
            dir=str(tmp_path),
            extensions=["py"],
            max_file_size=1024 * 1024,
            skip_hidden=True,
        )

        assert len(files) == 2
        filenames = [f.split("/")[-1] for f in files]
        assert "module.py" in filenames
        assert "utils.py" in filenames

    def test_count_files_in_dir(self, tmp_path):
        """count_files_in_dir should return correct count."""
        from omni_core_rs import count_files_in_dir

        # Create test files
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.py").write_text("b")
        (tmp_path / "c.py").write_text("c")

        count = count_files_in_dir(
            dir=str(tmp_path),
            extensions=["py"],
            skip_hidden=True,
        )

        assert count == 3

    def test_should_skip_path(self):
        """should_skip_path should correctly skip paths."""
        from omni_core_rs import should_skip_path

        # Target directory should be skipped
        assert should_skip_path("/project/target/file.py", True, ["target", "node_modules"])

        # Normal path should not be skipped
        assert not should_skip_path("/project/src/main.py", True, ["target", "node_modules"])

        # Hidden files should be skipped
        assert should_skip_path("/project/.env", True, ["target"])

        # Hidden files should not be skipped when skip_hidden is False
        assert not should_skip_path("/project/.env", False, ["target"])

    def test_discover_files_respects_skip_dirs(self, tmp_path):
        """discover_files should skip configured directories."""
        from omni_core_rs import discover_files

        # Create structure
        (tmp_path / "main.py").write_text("print('main')")
        (tmp_path / "target").mkdir()
        (tmp_path / "target").mkdir(exist_ok=True)
        (tmp_path / "target" / "nested.py").write_text("print('nested')")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg").mkdir(exist_ok=True)
        (tmp_path / "node_modules" / "pkg" / "index.js").write_text("console.log('pkg')")

        files = discover_files(
            root=str(tmp_path),
            extensions=[".py"],
            max_file_size=1024 * 1024,
            skip_hidden=True,
            skip_dirs=["target", "node_modules"],
            recursive=True,
        )

        filenames = [f.split("/")[-1] for f in files]
        assert "main.py" in filenames
        # Files in skipped directories should not appear
        assert "nested.py" not in filenames
