"""File Discovery and AST Chunking for Project Librarian."""

import json
import subprocess
from pathlib import Path
from typing import Any

from omni_core_rs import py_chunk_code

from .config import KnowledgeConfig


class FileIngestor:
    """Discover and chunk source files for knowledge indexing."""

    def __init__(self, config: KnowledgeConfig | None = None):
        """Initialize the file ingestor.

        Args:
            config: Knowledge configuration (uses default if None)
        """
        self.config = config or KnowledgeConfig()

    def _should_skip(self, path: Path) -> bool:
        """Check if a path should be skipped based on directory name."""
        return any(part in self.config.skip_dirs for part in path.parts)

    def discover_files(
        self,
        project_root: Path,
        max_files: int | None = None,
        use_knowledge_dirs: bool = True,
    ) -> list[Path]:
        """Discover source files for indexing.

        Args:
            project_root: Project root directory
            max_files: Maximum files to return (None for unlimited)
            use_knowledge_dirs: Use knowledge_dirs from config instead of git

        Returns:
            List of file paths to process
        """
        files: list[Path] = []

        if use_knowledge_dirs:
            # Use knowledge_dirs from references.yaml
            for kb_path in self.config.get_knowledge_paths(project_root):
                files.extend(self._discover_in_dir(kb_path))
        else:
            # Use git ls-files
            files = self._discover_via_git(project_root)

        # Apply limits
        if max_files and len(files) > max_files:
            files = files[:max_files]

        return sorted(set(files))

    def _discover_in_dir(self, directory: Path) -> list[Path]:
        """Discover files in a directory recursively."""
        if not directory.exists():
            return []

        files = []
        # Use ALL supported extensions (code + markdown)
        for ext in self.config.supported_extensions:
            for f in directory.rglob(f"*{ext}"):
                if (
                    f.is_file()
                    and not self._should_skip(f)
                    and f.stat().st_size <= self.config.max_file_size
                ):
                    files.append(f)
        return files

    def _discover_via_git(self, project_root: Path) -> list[Path]:
        """Discover files using git ls-files (respects .gitignore)."""
        try:
            result = subprocess.run(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            files = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                file_path = project_root / line
                if (
                    file_path.exists()
                    and not self._should_skip(file_path)
                    and file_path.stat().st_size <= self.config.max_file_size
                    and file_path.suffix.lower() in self.config.ast_extensions
                ):
                    files.append(file_path)
            return files
        except Exception:
            return []

    def chunk_file(self, file_path: Path, content: str) -> list[dict[str, Any]]:
        """Chunk a file using AST or fallback to text.

        Args:
            file_path: Path to the file
            content: File content

        Returns:
            List of chunks with id, content, metadata
        """
        ext = file_path.suffix.lower()
        language = self.config.ast_extensions.get(ext)

        if language:
            return self._ast_chunk(content, str(file_path), language)
        return self._text_chunk(content, str(file_path))

    def _ast_chunk(self, content: str, file_path: str, language: str) -> list[dict[str, Any]]:
        """Use Rust AST chunking for semantic code understanding."""
        try:
            patterns = self.config.ast_patterns.get(language, ["def $NAME", "class $NAME"])

            chunks = py_chunk_code(
                content=content,
                file_path=file_path,
                language=language,
                patterns=patterns,
                min_lines=1,
                max_lines=0,
            )

            return [
                {
                    "id": chunk.id,
                    "content": chunk.content,
                    "start_line": chunk.line_start,
                    "end_line": chunk.line_end,
                    "type": chunk.chunk_type,
                    "language": language,
                }
                for chunk in chunks
            ]
        except Exception:
            return self._text_chunk(content, file_path)

    def _text_chunk(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Fallback text-based chunking."""
        lines = content.split("\n")
        chunks = []
        chunk_size = 50  # lines per chunk

        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i : i + chunk_size]
            if not "".join(chunk_lines).strip():
                continue

            chunk_text = "\n".join(chunk_lines)
            chunk_id = f"{Path(file_path).stem}_{i // chunk_size}"

            chunks.append(
                {
                    "id": chunk_id,
                    "content": chunk_text,
                    "start_line": i + 1,
                    "end_line": min(i + chunk_size, len(lines)),
                    "type": "text",
                    "language": "",
                }
            )

        return chunks

    def create_records(
        self,
        files: list[Path],
        project_root: Path,
        mode: str = "auto",
    ) -> list[dict[str, Any]]:
        """Create indexed records from files.

        Args:
            files: List of file paths to process
            project_root: Project root directory
            mode: Chunking mode - "text", "ast", or "auto"

        Returns:
            List of records ready for embedding and storage
        """
        records = []

        for file_path in files:
            try:
                rel_path = str(file_path.relative_to(project_root))
                content = file_path.read_text(errors="ignore")

                if not content.strip():
                    continue

                chunks = self._chunk_with_mode(file_path, content, mode)

                for chunk in chunks:
                    record_id = f"{rel_path}:{chunk['start_line']}-{chunk['end_line']}"
                    records.append(
                        {
                            "id": record_id,
                            "text": chunk["content"],
                            "metadata": json.dumps(
                                {
                                    "file_path": rel_path,
                                    "start_line": chunk["start_line"],
                                    "end_line": chunk["end_line"],
                                    "chunk_type": chunk.get("type", "code"),
                                    "language": chunk.get("language", ""),
                                }
                            ),
                        }
                    )
            except Exception:
                continue

        return records

    def _chunk_with_mode(self, file_path: Path, content: str, mode: str) -> list[dict[str, Any]]:
        """Chunk a file using the specified mode.

        Args:
            file_path: Path to the file
            content: File content
            mode: "text", "ast", or "auto"

        Returns:
            List of chunks
        """
        ext = file_path.suffix.lower()
        is_markdown = ext in self.config.markdown_extensions

        if mode == "text" or is_markdown:
            # Text chunking for markdown and forced text mode
            return self._text_chunk(content, str(file_path))
        elif mode == "ast":
            # AST chunking for supported code languages
            language = self.config.ast_extensions.get(ext)
            if language:
                return self._ast_chunk(content, str(file_path), language)
            return self._text_chunk(content, str(file_path))
        else:
            # Auto mode: AST for code, text for markdown/docs
            language = self.config.ast_extensions.get(ext)
            if language:
                return self._ast_chunk(content, str(file_path), language)
            return self._text_chunk(content, str(file_path))
