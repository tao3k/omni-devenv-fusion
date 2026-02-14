"""File Discovery and AST Chunking for Project Librarian."""

import json
import subprocess
from pathlib import Path
from typing import Any

from omni_core_rs import py_chunk_code, py_extract_skeleton, discover_files, should_skip_path
from omni.foundation.runtime.path_filter import SKIP_DIRS as DEFAULT_SKIP_DIRS

from .config import KnowledgeConfig


class FileIngestor:
    """Discover and chunk source files for knowledge indexing."""

    def __init__(self, config: KnowledgeConfig | None = None):
        """Initialize the file ingestor.

        Args:
            config: Knowledge configuration (uses default if None)
        """
        self.config = config or KnowledgeConfig()
        # Build skip_dirs list for Rust functions
        self._skip_dirs = list(self.config.skip_dirs | DEFAULT_SKIP_DIRS)

    def _should_skip(self, path: Path) -> bool:
        """Check if a path should be skipped using Rust-based filtering."""
        return should_skip_path(
            str(path),
            skip_hidden=True,
            skip_dirs=self._skip_dirs,
        )

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
        """Discover files in a directory recursively using Rust-based discovery."""
        if not directory.exists():
            return []

        # Build skip_dirs from config + defaults
        skip_dirs = list(self.config.skip_dirs | DEFAULT_SKIP_DIRS)

        # Use Rust-based file discovery for performance
        extensions = [f".{ext.lstrip('.')}" for ext in self.config.supported_extensions]

        rust_files = discover_files(
            root=str(directory),
            extensions=extensions,
            max_file_size=self.config.max_file_size,
            skip_hidden=True,
            skip_dirs=skip_dirs,
            recursive=True,
        )

        # Convert to Path objects - Rust returns paths relative to root,
        # so we need to join with directory to get absolute paths
        return [directory / f for f in rust_files]

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

    def _skeleton_chunk(self, content: str, file_path: str, language: str) -> list[dict[str, Any]]:
        """Extract skeleton (signatures only) for lightweight semantic indexing.

        This uses Rust's extract_skeleton which:
        1. Parses AST to find function/class signatures
        2. Removes implementation bodies
        3. Preserves docstrings
        4. Returns highly compressed representation for embedding
        """
        try:
            result = py_extract_skeleton(content, language)
            data = json.loads(result)

            skeleton = data.get("skeleton", "")

            if not skeleton.strip():
                return self._text_chunk(content, file_path)

            # Split skeleton into individual items
            items = skeleton.split("\n\n")

            chunks = []
            for i, item in enumerate(items):
                item = item.strip()
                if not item:
                    continue

                # Generate a pseudo line range for compatibility
                chunk_id = f"{Path(file_path).stem}_skel_{i}"

                chunks.append(
                    {
                        "id": chunk_id,
                        "content": item,
                        "start_line": 1,  # Skeleton doesn't track line numbers
                        "end_line": 1,
                        "type": "skeleton",
                        "language": language,
                    }
                )

            return chunks
        except Exception:
            return self._text_chunk(content, file_path)

    def _markdown_section_chunk(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Section-aware chunking for markdown: split by ## / ### for precise retrieval.

        Each section (with its header) becomes a chunk; long sections are sub-split
        by max_section_lines so we avoid mega-chunks that match too many queries.
        """
        lines = content.split("\n")
        chunks: list[dict[str, Any]] = []
        max_section_lines = 60
        current_header = ""
        section_start = 0
        section_lines: list[str] = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            is_header = stripped.startswith("## ") or stripped.startswith("### ")
            if is_header and section_lines:
                chunk_text = "\n".join(section_lines)
                if chunk_text.strip():
                    chunk_id = f"{Path(file_path).stem}_s{len(chunks)}"
                    chunks.append(
                        {
                            "id": chunk_id,
                            "content": chunk_text,
                            "start_line": section_start + 1,
                            "end_line": section_start + len(section_lines),
                            "type": "section",
                            "language": "",
                        }
                    )
                section_start = i
                section_lines = [line]
                current_header = stripped
            elif is_header:
                section_start = i
                section_lines = [line]
                current_header = stripped
            else:
                section_lines.append(line)
                if len(section_lines) >= max_section_lines:
                    chunk_text = "\n".join(section_lines)
                    if chunk_text.strip():
                        chunk_id = f"{Path(file_path).stem}_s{len(chunks)}"
                        chunks.append(
                            {
                                "id": chunk_id,
                                "content": chunk_text,
                                "start_line": section_start + 1,
                                "end_line": section_start + len(section_lines),
                                "type": "section",
                                "language": "",
                            }
                        )
                    section_start = i + 1
                    section_lines = []

        if section_lines:
            chunk_text = "\n".join(section_lines)
            if chunk_text.strip():
                chunk_id = f"{Path(file_path).stem}_s{len(chunks)}"
                chunks.append(
                    {
                        "id": chunk_id,
                        "content": chunk_text,
                        "start_line": section_start + 1,
                        "end_line": section_start + len(section_lines),
                        "type": "section",
                        "language": "",
                    }
                )
        return chunks if chunks else self._text_chunk(content, file_path)

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

    def _summary_chunk(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Create a summary-only chunk for lightweight embedding.

        Extracts:
        - Filename
        - First H1 header (title)
        - First 500 chars of content as summary

        This reduces token usage by ~95% for knowledge base indexing.
        """
        filename = Path(file_path).stem
        title = ""
        summary_chars = 500

        # Extract first H1 header (markdown title)
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
                break

        # Create summary from first N characters
        first_chars = content[:summary_chars]
        # Trim to last complete sentence or line
        summary = first_chars.rsplit("\n", 1)[0].rsplit(". ", 1)[0]

        # Build semantic anchor text
        semantic_text = f"File: {filename}\n"
        if title:
            semantic_text += f"Title: {title}\n"
        semantic_text += f"Summary: {summary}..."

        return [
            {
                "id": f"{Path(file_path).stem}_summary",
                "content": semantic_text,
                "start_line": 1,
                "end_line": 1,
                "type": "summary",
                "language": "",
            }
        ]

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
            mode: "text", "skeleton", "ast", "summary", or "auto"

        Returns:
            List of chunks
        """
        ext = file_path.suffix.lower()
        is_markdown = ext in self.config.markdown_extensions

        if mode == "text":
            # Full text chunking
            return self._text_chunk(content, str(file_path))
        elif mode == "summary":
            # Summary-only chunking for lightweight embedding
            return self._summary_chunk(content, str(file_path))
        elif mode == "auto" and is_markdown:
            # Section-aware chunking for precise retrieval (one chunk per ## section)
            return self._markdown_section_chunk(content, str(file_path))
        elif mode == "skeleton":
            # Skeleton mode for lightweight semantic indexing (default for code)
            language = self.config.ast_extensions.get(ext)
            if language:
                return self._skeleton_chunk(content, str(file_path), language)
            return self._text_chunk(content, str(file_path))
        elif mode == "ast":
            # AST chunking for supported code languages
            language = self.config.ast_extensions.get(ext)
            if language:
                return self._ast_chunk(content, str(file_path), language)
            return self._text_chunk(content, str(file_path))
        else:
            # Auto mode: section chunking for markdown, skeleton for code
            if is_markdown:
                return self._markdown_section_chunk(content, str(file_path))
            language = self.config.ast_extensions.get(ext)
            if language:
                return self._skeleton_chunk(content, str(file_path), language)
            return self._text_chunk(content, str(file_path))
