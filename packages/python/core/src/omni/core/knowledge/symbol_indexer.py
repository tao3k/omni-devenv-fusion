"""
Zero-Token Indexer using Rust-native AST extraction.

Replaces expensive LLM summarization for code artifacts.
Uses omni-tags (Rust) for symbol extraction without LLM tokens.

Architecture:
    SymbolIndexer (main class)
        ├── omni_tags: Rust bindings for AST extraction
        ├── Symbol Map: {symbol_name -> [(file_path, line, kind)]}
        └── Inverted Index: {file_path -> [symbols]}

Usage:
    from omni.core.knowledge.symbol_indexer import SymbolIndexer

    # Build symbol index for a project
    indexer = SymbolIndexer(project_root=".")
    indexer.build()

    # Query symbols
    results = indexer.search_symbol("OmniLoop")
    # Returns: [{"file": "src/main.py", "line": 42, "kind": "class"}]
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

try:
    import omni_core_rs as omni_rs
except ImportError:
    omni_rs = None

from .config import KnowledgeConfig
from omni.foundation.runtime.path_filter import should_skip_path, SKIP_DIRS

logger = logging.getLogger(__name__)


class Symbol:
    """Represents a code symbol extracted from source."""

    def __init__(
        self,
        name: str,
        kind: str,
        line: int,
        signature: str,
        file_path: str,
    ):
        self.name = name
        self.kind = kind
        self.line = line
        self.signature = signature
        self.file_path = file_path

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "line": self.line,
            "signature": self.signature,
            "file": self.file_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], file_path: str) -> "Symbol":
        return cls(
            name=data.get("name", ""),
            kind=data.get("kind", ""),
            line=data.get("line", 0),
            signature=data.get("signature", ""),
            file_path=file_path,
        )


class SymbolIndex:
    """In-memory symbol index for fast lookups."""

    def __init__(self):
        # symbol_name -> list of (file_path, line, kind)
        self._symbol_to_locations: dict[str, list[tuple[str, int, str]]] = {}
        # file_path -> list of symbol names
        self._file_to_symbols: dict[str, list[str]] = {}
        # file_path -> dict with symbols info
        self._file_metadata: dict[str, dict[str, Any]] = {}

    def add_symbol(self, symbol: Symbol) -> None:
        """Add a symbol to the index."""
        # Update symbol -> locations mapping
        if symbol.name not in self._symbol_to_locations:
            self._symbol_to_locations[symbol.name] = []
        self._symbol_to_locations[symbol.name].append((symbol.file_path, symbol.line, symbol.kind))

        # Update file -> symbols mapping
        if symbol.file_path not in self._file_to_symbols:
            self._file_to_symbols[symbol.file_path] = []
        if symbol.name not in self._file_to_symbols[symbol.file_path]:
            self._file_to_symbols[symbol.file_path].append(symbol.name)

    def lookup(self, symbol_name: str) -> list[dict[str, Any]]:
        """Find all locations where a symbol is defined."""
        locations = self._symbol_to_locations.get(symbol_name, [])
        return [{"file": path, "line": line, "kind": kind} for path, line, kind in locations]

    def get_file_symbols(self, file_path: str) -> list[str]:
        """Get all symbols in a file."""
        return self._file_to_symbols.get(file_path, [])

    def get_all_symbols(self) -> dict[str, list[dict[str, Any]]]:
        """Get the entire index."""
        return {
            name: [{"file": path, "line": line, "kind": kind} for path, line, kind in locations]
            for name, locations in self._symbol_to_locations.items()
        }

    def stats(self) -> dict[str, int]:
        """Get index statistics."""
        return {
            "unique_symbols": len(self._symbol_to_locations),
            "indexed_files": len(self._file_to_symbols),
        }


class SymbolIndexer:
    """
    Zero-Token Indexer using Rust-native AST extraction.

    Extracts symbols (functions, classes, etc.) from code without using LLM.
    Uses omni-tags (Rust bindings) for high-performance AST parsing.

    Features:
    - Zero LLM tokens for indexing
    - Supports Python, Rust, JavaScript, TypeScript
    - Incremental updates (re-index only changed files)
    - Fast symbol lookup
    """

    def __init__(
        self,
        project_root: str | Path = ".",
        extensions: list[str] | None = None,
    ):
        """
        Initialize the SymbolIndexer.

        Args:
            project_root: Root directory of the project to index.
            extensions: File extensions to index (default: py, rs, js, ts).
        """
        from omni.foundation.config.dirs import get_vector_db_path

        self.root = Path(project_root).resolve()
        self.extensions = extensions or [".py", ".rs", ".js", ".ts"]
        self.index = SymbolIndex()
        self._manifest: dict[str, str] = {}  # file_path -> content_hash

        # Store manifest in .cache/omni-vector/ alongside other indexes
        vector_dir = get_vector_db_path()
        self._manifest_file = vector_dir / "symbol_manifest.json"

        if omni_rs is None:
            logger.warning("omni_core_rs not available, symbol indexing disabled")

    def _compute_hash(self, content: str) -> str:
        """Compute hash for content using Rust xxhash (5-10x faster than MD5)."""
        if omni_rs is None:
            import hashlib

            return hashlib.md5(content.encode("utf-8")).hexdigest()
        return omni_rs.compute_hash(content)

    def _is_supported_file(self, path: Path) -> bool:
        """Check if file has a supported extension."""
        return path.suffix in self.extensions

    def _find_code_files(self) -> list[Path]:
        """Find all code files using fd for fast file discovery."""
        import subprocess

        code_files = []
        seen = set()  # Deduplicate files

        # Get skip_dirs from config, merged with defaults
        config = KnowledgeConfig()
        skip_dirs = SKIP_DIRS | config.skip_dirs

        def should_skip(path: Path) -> bool:
            """Check if path should be skipped (hidden files/dirs or skip names)."""
            return should_skip_path(path, skip_hidden=True, skip_dirs=skip_dirs)

        code_dirs = config.ast_symbols_dirs

        # Check if any configured directories exist in the project root
        configured_dirs_exist = False
        if code_dirs:
            for entry in code_dirs:
                dir_path = self.root / entry.get("path", "")
                if dir_path.exists():
                    configured_dirs_exist = True
                    break

        if code_dirs and configured_dirs_exist:
            # Use configured directories with fd
            for entry in code_dirs:
                dir_path = self.root / entry.get("path", "")
                globs = entry.get("globs", [])

                # Skip if directory doesn't exist
                if not dir_path.exists():
                    continue

                # Support both single glob and list of globs
                if isinstance(globs, str):
                    globs = [globs]

                for glob_pattern in globs:
                    # Convert glob pattern to fd pattern
                    ext_pattern = glob_pattern
                    if glob_pattern.startswith("**/*"):
                        ext_pattern = glob_pattern[4:]  # Remove **/
                    elif glob_pattern.startswith("*"):
                        ext_pattern = glob_pattern[1:]  # Remove *

                    # Use fd to find files
                    try:
                        result = subprocess.run(
                            ["fd", ext_pattern, str(dir_path), "--max-depth", "10", "-t", "f"],
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if result.returncode == 0:
                            for line in result.stdout.strip().splitlines():
                                if line:
                                    f = Path(line)
                                    if should_skip(f):
                                        continue
                                    if f not in seen:
                                        seen.add(f)
                                        code_files.append(f)
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        # Fallback to glob if fd fails
                        for f in dir_path.glob(glob_pattern):
                            if should_skip(f):
                                continue
                            if f.is_file() and f not in seen:
                                seen.add(f)
                                code_files.append(f)
        else:
            # Fallback to extensions-based discovery using fd (search in project root)
            for ext in self.extensions:
                ext_pattern = ext.lstrip(".")  # fd uses extension without dot
                if ext_pattern:
                    try:
                        result = subprocess.run(
                            [
                                "fd",
                                f"{ext_pattern}$",
                                str(self.root),
                                "--max-depth",
                                "10",
                                "-t",
                                "f",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )
                        if result.returncode == 0:
                            for line in result.stdout.strip().splitlines():
                                if line:
                                    f = Path(line)
                                    if should_skip(f):
                                        continue
                                    if f not in seen:
                                        seen.add(f)
                                        code_files.append(f)
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        # Fallback to rglob if fd fails
                        for f in self.root.rglob(f"*{ext}"):
                            if should_skip(f):
                                continue
                            if f.is_file() and f not in seen:
                                seen.add(f)
                                code_files.append(f)

        return code_files

    def _parse_outline(self, outline: str, file_path: str) -> list[Symbol]:
        """
        Parse outline output into Symbol objects.

        Args:
            outline: Outline string from Rust
            file_path: Relative file path for the symbols

        Returns:
            List of Symbol objects.
        """
        symbols = []

        if outline.startswith("[Error") or outline.startswith("[No outline"):
            return []

        # Parse the outline output format
        # Format: "L{line} [{kind}] {name} {signature}"
        for line in outline.splitlines():
            if not line.startswith("L"):
                continue

            parts = line.split(None, 3)  # Split into max 4 parts
            if len(parts) < 4:
                continue

            try:
                line_num = int(parts[0][1:])  # Remove 'L' prefix
                kind = parts[1].strip("[]")
                name = parts[2]
                signature = parts[3] if len(parts) > 3 else name

                symbols.append(
                    Symbol(
                        name=name,
                        kind=kind,
                        line=line_num,
                        signature=signature,
                        file_path=file_path,
                    )
                )
            except (ValueError, IndexError):
                continue

        return symbols

    def _extract_symbols_batch(self, file_paths: list[Path]) -> dict[str, list[Symbol]]:
        """
        Extract symbols from multiple files using batch Rust API.

        This is much faster than calling get_file_outline() for each file
        because it eliminates Python-Rust boundary crossing overhead.

        Args:
            file_paths: List of file paths to process

        Returns:
            Dict mapping relative file path to list of Symbol objects.
        """
        if omni_rs is None:
            return {}

        if not file_paths:
            return {}

        # Prepare paths
        abs_paths = [str(f) for f in file_paths]

        # Use batch API
        result = omni_rs.get_files_outline(abs_paths)

        # Parse JSON result
        import json

        try:
            outlines = json.loads(result)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse batch outline result")
            return {}

        # Parse outlines into symbols
        symbols_map = {}
        for abs_path, outline in outlines.items():
            try:
                rel_path = str(Path(abs_path).relative_to(self.root))
            except ValueError:
                rel_path = abs_path

            symbols = self._parse_outline(outline, rel_path)
            if symbols:
                symbols_map[rel_path] = symbols

        return symbols_map

    def _extract_symbols_from_file(self, file_path: Path) -> list[Symbol]:
        """
        Extract symbols from a single file using omni-tags.

        Returns:
            List of Symbol objects.
        """
        if omni_rs is None:
            return []

        symbols = []
        abs_path = str(file_path)
        try:
            rel_path = str(file_path.relative_to(self.root))
        except ValueError:
            # File is outside project root, use absolute path as key
            rel_path = abs_path

        try:
            # Use Rust binding to get file outline
            result = omni_rs.get_file_outline(abs_path)
            symbols = self._parse_outline(result, rel_path)
        except Exception as e:
            logger.warning(f"Error extracting symbols from {abs_path}: {e}")

        return symbols

    def build(self, clean: bool = False) -> dict[str, int]:
        """
        Build the symbol index for the entire project.

        Args:
            clean: If True, rebuild from scratch. If False, only changed files.

        Returns:
            Dictionary with indexed_files and unique_symbols count.
        """
        import json

        if omni_rs is None:
            logger.error("omni_core_rs not available")
            return {"indexed_files": 0, "unique_symbols": 0}

        logger.info(f"Building symbol index for {self.root}")

        if clean:
            self.index = SymbolIndex()
            self._manifest = {}

        # Find all code files
        code_files = self._find_code_files()
        logger.info(f"Found {len(code_files)} code files")

        # Collect files that need processing (changed or new)
        files_to_process: list[Path] = []
        file_hashes: dict[str, str] = {}

        for file_path in code_files:
            rel_path = str(file_path.relative_to(self.root))

            try:
                content = file_path.read_text(errors="ignore")
                file_hash = self._compute_hash(content)

                # Skip unchanged files
                if not clean and self._manifest.get(rel_path) == file_hash:
                    continue

                files_to_process.append(file_path)
                file_hashes[rel_path] = file_hash

            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to read {rel_path}: {e}")

        # Batch extract symbols for changed/new files
        symbols_map: dict[str, list[Symbol]] = {}
        if files_to_process:
            logger.info(f"Extracting symbols from {len(files_to_process)} files (batch mode)")

            # Use batch API for faster extraction
            symbols_map = self._extract_symbols_batch(files_to_process)

            # Add symbols to index
            for rel_path, symbols in symbols_map.items():
                # Remove old symbols for this file
                old_symbols = self.index.get_file_symbols(rel_path)
                for sym_name in old_symbols:
                    if sym_name in self.index._symbol_to_locations:
                        locations = self.index._symbol_to_locations[sym_name]
                        self.index._symbol_to_locations[sym_name] = [
                            loc for loc in locations if loc[0] != rel_path
                        ]
                        if not self.index._symbol_to_locations[sym_name]:
                            del self.index._symbol_to_locations[sym_name]

                # Add new symbols
                for symbol in symbols:
                    self.index.add_symbol(symbol)

                # Update manifest
                if rel_path in file_hashes:
                    self._manifest[rel_path] = file_hashes[rel_path]

        # All processed files are already in manifest via file_hashes
        indexed_count = len(files_to_process)

        # Save manifest
        self._save_manifest()

        stats = self.index.stats()
        stats["indexed_files"] = indexed_count
        logger.info(
            f"Symbol index built: {stats['indexed_files']} files, "
            f"{stats['unique_symbols']} unique symbols"
        )

        return stats

    def _save_manifest(self) -> None:
        """Save the manifest to disk."""
        manifest_dir = self._manifest_file.parent
        manifest_dir.mkdir(parents=True, exist_ok=True)
        import json

        self._manifest_file.write_text(json.dumps(self._manifest, indent=2))

    def load_manifest(self) -> None:
        """Load the manifest from disk."""
        if self._manifest_file.exists():
            import json

            try:
                self._manifest = json.loads(self._manifest_file.read_text())
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load manifest: {e}")
                self._manifest = {}

    def search_symbol(self, name: str) -> list[dict[str, Any]]:
        """
        Search for a symbol by name.

        Args:
            name: Symbol name to search for.

        Returns:
            List of locations where the symbol is defined.
        """
        return self.index.lookup(name)

    def search_pattern(self, pattern: str) -> list[dict[str, Any]]:
        """
        Search for symbols matching a pattern (glob-style).

        Args:
            pattern: Pattern to match (supports * wildcards).

        Returns:
            List of matching symbols with locations.
        """
        import fnmatch

        results = []
        for symbol_name, locations in self.index._symbol_to_locations.items():
            if fnmatch.fnmatch(symbol_name, pattern):
                for path, line, kind in locations:
                    results.append(
                        {
                            "name": symbol_name,
                            "file": path,
                            "line": line,
                            "kind": kind,
                        }
                    )
        return results

    def get_file_symbols(self, file_path: str) -> list[dict[str, Any]]:
        """
        Get all symbols in a specific file.

        Args:
            file_path: Relative path to the file.

        Returns:
            List of symbols in the file.
        """
        symbols = self.index.get_file_symbols(file_path)
        return [
            {"name": name, "line": loc[1], "kind": loc[2]}
            for name in symbols
            for loc in self.index._symbol_to_locations.get(name, [])
            if loc[0] == file_path
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        return self.index.stats()

    def export_index(self) -> dict[str, Any]:
        """Export the full index as a dictionary."""
        return {
            "symbols": self.index.get_all_symbols(),
            "stats": self.get_stats(),
        }

    def clear(self) -> None:
        """Clear the index and manifest."""
        self.index = SymbolIndex()
        self._manifest = {}
        if self._manifest_file.exists():
            self._manifest_file.unlink()


# Convenience functions
def build_symbol_index(
    project_root: str | Path = ".",
    extensions: list[str] | None = None,
) -> SymbolIndexer:
    """
    Build a symbol index for a project.

    Args:
        project_root: Root directory of the project.
        extensions: File extensions to index.

    Returns:
        SymbolIndexer instance with built index.
    """
    indexer = SymbolIndexer(project_root, extensions)
    indexer.build(clean=True)
    return indexer


__all__ = [
    "Symbol",
    "SymbolIndex",
    "SymbolIndexer",
    "build_symbol_index",
]
