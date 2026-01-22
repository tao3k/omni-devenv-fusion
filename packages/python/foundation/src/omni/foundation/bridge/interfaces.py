"""
interfaces.py - Protocol Definitions for Bridge Layer

Defines abstract interfaces (Protocols) that specify "what we need"
rather than "what Rust provides". This decouples the implementation
from the interface definition.
"""

from __future__ import annotations

from typing import Protocol


class VectorStoreProvider(Protocol):
    """Interface for vector database operations.

    Defines the contract for semantic search and document ingestion.
    """

    async def search(
        self,
        query: str,
        limit: int = 5,
        filters: Dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents using vector similarity."""
        ...

    async def ingest(self, content: FileContent) -> IngestResult:
        """Ingest a document into the vector store."""
        ...

    async def delete(self, document_id: str) -> bool:
        """Delete a document from the vector store."""
        ...

    async def create_index(
        self,
        name: str,
        dimension: int,
        path: str | None = None,
    ) -> bool:
        """Create a new vector index."""
        ...

    async def health_check(self) -> bool:
        """Check if the vector store is healthy."""
        ...


class CodeAnalysisProvider(Protocol):
    """Interface for code analysis and AST operations.

    Provides pattern matching and symbol extraction from source code.
    """

    def find_patterns(
        self,
        code: str,
        pattern: str,
        language: str = "python",
    ) -> list[Dict[str, Any]]:
        """Find AST patterns in source code."""
        ...

    def extract_symbols(
        self,
        code: str,
        language: str = "python",
    ) -> list[CodeSymbol]:
        """Extract all symbols (functions, classes, etc.) from source code."""
        ...

    def count_lines_of_code(
        self,
        code: str,
        language: str | None = None,
    ) -> Dict[str, int]:
        """Count lines of code by category (blank, comment, code)."""
        ...

    def get_file_outline(
        self,
        code: str,
        language: str = "python",
    ) -> Dict[str, Any]:
        """Generate a high-level outline of the source file."""
        ...


class FileScannerProvider(Protocol):
    """Interface for file system scanning operations.

    Provides recursive directory scanning with filtering.
    """

    def scan_directory(
        self,
        path: str,
        pattern: str | None = None,
        max_depth: int | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[str]:
        """Scan a directory and return matching file paths."""
        ...

    def get_file_info(self, path: str) -> Dict[str, Any] | None:
        """Get metadata about a file."""
        ...

    def is_safe_path(self, base_path: str, target_path: str) -> bool:
        """Check if a target path is within the base path (prevent path traversal)."""
        ...


class SkillScannerProvider(Protocol):
    """Interface for skill-specific scanning operations.

    Parses skill structures and extracts metadata.
    """

    def scan_skill(self, skill_path: str) -> SkillStructure:
        """Scan a skill directory and extract its structure."""
        ...

    def parse_skill_metadata(self, skill_path: str) -> Dict[str, Any]:
        """Parse the SKILL.md YAML frontmatter."""
        ...

    def extract_scripts(self, skill_path: str) -> list[str]:
        """Extract Python scripts from the skill's scripts directory."""
        ...

    def find_skill_references(self, skill_path: str) -> list[str]:
        """Find all references mentioned in the skill."""
        ...


__all__ = [
    "VectorStoreProvider",
    "CodeAnalysisProvider",
    "FileScannerProvider",
    "SkillScannerProvider",
]
