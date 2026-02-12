"""
test_librarian_scenario.py - Integration Tests for Librarian

Tests for the unified Librarian with text and AST chunking modes.
"""

from pathlib import Path
import subprocess

import pytest


class MockEmbeddingService:
    """Mock embedding service for testing (sync API to match real EmbeddingService)."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.backend = "mock"
        self._load_local_model = False  # Attribute needed by Librarian

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate deterministic embeddings based on text content."""
        import hashlib

        embeddings = []
        for text in texts:
            hash_bytes = hashlib.sha256(text.encode()).digest()
            vector = [float(b) / 255.0 for b in hash_bytes]
            while len(vector) < self.dimension:
                vector.extend(vector)
            embeddings.append(vector[: self.dimension])

        return embeddings

    def embed(self, query: str) -> list[list[float]]:
        """Embed a single query (returns list of lists to match real EmbeddingService)."""
        return self.embed_batch([query])


@pytest.fixture
def mock_embedder():
    """Create a mock embedding service."""
    return MockEmbeddingService()


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project with sample code."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()

    # Python file with functions and classes
    py_file = project_root / "calculator.py"
    py_file.write_text('''
def add(a, b):
    """Add two numbers."""
    return a + b

def subtract(a, b):
    """Subtract b from a."""
    return a - b

class MathOps:
    """Advanced math operations."""

    def multiply(self, x, y):
        """Multiply two numbers."""
        return x * y

    def divide(self, x, y):
        """Divide x by y."""
        if y == 0:
            raise ValueError("Cannot divide by zero")
        return x / y
''')

    # Rust file
    rs_file = project_root / "lib.rs"
    rs_file.write_text("""
pub fn hello(name: &str) -> String {
    format!("Hello, {}!", name)
}

pub struct Greeter {
    name: String,
}

impl Greeter {
    pub fn new(name: String) -> Self {
        Self { name }
    }
}
""")

    # Markdown file
    md_file = project_root / "README.md"
    md_file.write_text("# Test Project\n\nThis is a test project for Librarian.\n")

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=project_root, capture_output=True)

    return project_root


@pytest.fixture
def librarian_store(tmp_path):
    """Create a temporary vector store."""
    from omni_core_rs import PyVectorStore

    store_path = str(tmp_path / "test_librarian.lance")
    store = PyVectorStore(store_path, 384, True)
    return store


class TestLibrarian:
    """Tests for the unified Librarian class."""

    @pytest.mark.asyncio
    async def test_full_ingestion_flow(self, temp_project, librarian_store, mock_embedder):
        """Test complete ingestion flow from files to indexed chunks."""
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(
            project_root=str(temp_project),
            store=librarian_store,
            embedder=mock_embedder,
            use_knowledge_dirs=False,
        )

        result = await librarian._ingest_async(clean=True)

        # Only .py and .rs files are discovered (README.md is not in ast_extensions)
        assert result["files_processed"] == 2, f"Expected 2 files, got {result['files_processed']}"
        assert result["chunks_indexed"] > 0, "Expected at least one chunk"

    @pytest.mark.asyncio
    async def test_ast_chunking_python(self, temp_project, librarian_store, mock_embedder):
        """Test that AST chunking correctly identifies Python functions and classes."""
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(
            project_root=str(temp_project),
            store=librarian_store,
            embedder=mock_embedder,
            use_knowledge_dirs=False,
        )

        await librarian._ingest_async(clean=True)
        results = librarian.query("multiply", limit=5)

        assert len(results) > 0, "Expected to find 'multiply'"

        # Rust store returns 'content' field, not 'text'
        found_multiply = any(
            "multiply" in res.get("content", res.get("text", "")) for res in results
        )
        assert found_multiply, "Expected to find multiply in results"

    @pytest.mark.asyncio
    async def test_ast_chunking_rust(self, temp_project, librarian_store, mock_embedder):
        """Test that AST chunking works for Rust code."""
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(
            project_root=str(temp_project),
            store=librarian_store,
            embedder=mock_embedder,
            use_knowledge_dirs=False,
        )

        await librarian._ingest_async(clean=True)

        results = librarian.query("Greeter", limit=20)

        # Check that at least one result contains Rust code from lib.rs
        rust_results = []
        for r in results:
            # Handle metadata - it could be a dict or a JSON string
            meta = r.get("metadata", {})
            if isinstance(meta, str):
                import json

                try:
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            file_path = meta.get("file_path", "") if isinstance(meta, dict) else ""
            if file_path.endswith(".rs"):
                rust_results.append(r)

        assert len(rust_results) > 0, f"Expected Rust results"

        # Verify the impl block with Greeter is indexed
        found_greeter = any("Greeter" in res.get("content", "") for res in rust_results)
        assert found_greeter, f"Expected 'Greeter' in Rust results"

    @pytest.mark.asyncio
    async def test_get_context_formats_correctly(
        self, temp_project, librarian_store, mock_embedder
    ):
        """Test that get_context returns properly formatted LLM context."""
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(
            project_root=str(temp_project),
            store=librarian_store,
            embedder=mock_embedder,
            use_knowledge_dirs=False,
        )

        await librarian._ingest_async(clean=True)
        context = librarian.get_context("multiply", limit=2)

        assert context, "Expected non-empty context"
        assert "```" in context, "Expected code blocks in context"
        assert "calculator.py" in context, "Expected file path in context"

    @pytest.mark.asyncio
    async def test_query_with_metadata(self, temp_project, librarian_store, mock_embedder):
        """Test that query results include proper metadata."""
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(
            project_root=str(temp_project),
            store=librarian_store,
            embedder=mock_embedder,
            use_knowledge_dirs=False,
        )

        await librarian._ingest_async(clean=True)
        results = librarian.query("add", limit=5)

        for res in results:
            assert "id" in res, "Result should have id"
            # Rust store returns 'content' field, not 'text'
            assert "content" in res or "text" in res, "Result should have content or text"
            assert "metadata" in res, "Result should have metadata"

            metadata = res["metadata"]
            assert "file_path" in metadata, "Metadata should have file_path"
            assert "start_line" in metadata, "Metadata should have start_line"
            assert "chunk_type" in metadata, "Metadata should have chunk_type"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
