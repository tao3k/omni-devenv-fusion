"""
Dependency Indexer for Rust Crates.

Automatically indexes external Rust crate APIs from Cargo.toml dependencies
for fast API lookup without reading cargo docs or source files.

Architecture:
    DependencyIndexer
        ├── Cargo.toml Parser
        ├── Registry Locator (finds sources in ~/.cargo/registry/src/)
        ├── Symbol Extractor (reuses SymbolIndexer)
        └── ExternalSymbolStore (persistent storage)

Usage:
    # Index all dependencies
    indexer = DependencyIndexer()
    indexer.index_project("path/to/Cargo.toml")

    # Search for API
    results = indexer.search("*Dataset::new*")

    # Get specific symbol info
    symbol = indexer.get_symbol("lance", "Dataset")
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.dependency_indexer")


@dataclass
class CrateInfo:
    """Information about a single crate dependency."""

    name: str
    version: str
    path: Path | None = None
    symbols: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SymbolLocation:
    """Location of a symbol in a crate."""

    crate: str
    version: str
    name: str
    file_path: str
    line: int
    kind: str
    signature: str


class DependencyIndexer:
    """
    Index Rust crate dependencies for fast API lookup.

    Reads Cargo.toml dependencies, locates sources in cargo registry,
    and extracts public API symbols for quick searching.
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
    ):
        """Initialize the dependency indexer.

        Args:
            cache_dir: Directory to store indexed data (default: ~/.cache/omni-vector)
        """
        from omni.foundation.config.dirs import get_cache_dir

        self.cache_dir = cache_dir or get_cache_dir()
        self._external_index: dict[str, CrateInfo] = {}
        self._symbol_lookup: dict[str, list[SymbolLocation]] = {}

        # Ensure cache dir exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self.cache_dir / "external_crates_index.json"

    def _find_cargo_registry(self) -> Path | None:
        """Find the cargo registry source directory.

        Returns:
            Path to ~/.cargo/registry/src/ or None if not found
        """
        cargo_home = Path.home() / ".cargo"
        registry_src = cargo_home / "registry" / "src"

        if registry_src.exists():
            return registry_src

        # Try alternative locations
        for path in [
            Path("/root/.cargo/registry/src"),
            Path("/usr/local/cargo/registry/src"),
        ]:
            if path.exists():
                return path

        return None

    def _find_crate_in_registry(self, name: str, version: str) -> Path | None:
        """Find a crate source directory in the registry.

        Args:
            name: Crate name (e.g., "lance", "tantivy")
            version: Crate version (e.g., "0.16.0", "0.25")

        Returns:
            Path to crate source directory or None
        """
        registry = self._find_cargo_registry()
        if registry is None:
            logger.warning("Cargo registry not found")
            return None

        # Find the registry index directory
        registry_index = None
        for path in registry.iterdir():
            if path.is_dir() and path.name.startswith("index.crates.io-"):
                registry_index = path
                break

        if registry_index is None:
            return None

        # Look for the crate with version matching
        # Handle versions like "0.25" matching "0.25.0" or exact matches
        for subdir in registry_index.iterdir():
            if not subdir.is_dir():
                continue

            dir_name = subdir.name
            # Match: name-version (e.g., "lance-0.25.0")
            if dir_name.startswith(f"{name}-"):
                dir_version = dir_name[len(name) + 1 :]  # Extract version part

                # Check if versions match (handle "0.25" vs "0.25.0")
                if self._versions_match(version, dir_version):
                    logger.debug(f"Found {name} v{dir_version} in registry")
                    return subdir

        return None

    def _versions_match(self, requested: str, available: str) -> bool:
        """Check if version strings match.

        Handles:
        - Exact match: "0.25.0" == "0.25.0"
        - Partial match: "0.25" matches "0.25.0"
        - Pre-release: "7.0.0-rc2" matches directories containing the suffix
        """
        # Remove leading 'v' if present
        requested = requested.lstrip("v")
        available = available.lstrip("v")

        # Exact match
        if requested == available:
            return True

        # Partial version match (requested "0.25" matches available "0.25.0")
        if available.startswith(requested + "."):
            return True

        # Handle pre-release versions
        if "-" in requested:
            # Try to find a directory that contains the pre-release suffix
            if requested in available or available.startswith(requested.split("-")[0]):
                return True

        return False

    def _parse_cargo_toml(self, cargo_path: Path) -> dict[str, tuple[str, str]]:
        """Parse Cargo.toml and extract dependencies.

        Args:
            cargo_path: Path to Cargo.toml

        Returns:
            Dict of {crate_name: (version, source_type)}
            source_type: "crates.io", "git", "path", "unknown"
        """
        dependencies = {}

        if not cargo_path.exists():
            logger.error(f"Cargo.toml not found: {cargo_path}")
            return dependencies

        content = cargo_path.read_text()

        # Parse [dependencies] section
        dep_section = re.search(r"\[dependencies\](.*?)(?:\n\[|\Z)", content, re.DOTALL)
        if not dep_section:
            return dependencies

        for line in dep_section.group(1).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Match patterns:
            # crate_name = "version"
            # crate_name = { version = "version", features = [...] }
            # crate_name = { git = "url" }

            # Simple version pattern
            match = re.match(r'^(\w+)\s*=\s*"([^"]+)"', line)
            if match:
                name, version = match.groups()
                dependencies[name] = (version, "crates.io")
                continue

            # Git pattern
            match = re.match(r'^(\w+)\s*=\s*\{[^}]*git\s*=\s*"([^"]+)"', line)
            if match:
                name, git_url = match.groups()
                dependencies[name] = (git_url, "git")
                continue

            # Complex pattern with version
            match = re.match(r'^(\w+)\s*=\s*\{[^}]*version\s*=\s*"([^"]+)"', line)
            if match:
                name, version = match.groups()
                dependencies[name] = (version, "crates.io")
                continue

        return dependencies

    def _extract_symbols_from_crate(
        self, crate_path: Path, crate_name: str, version: str
    ) -> list[SymbolLocation]:
        """Extract public symbols from a crate.

        Args:
            crate_path: Path to crate source directory
            crate_name: Name of the crate
            version: Version string

        Returns:
            List of SymbolLocation objects
        """
        from omni.core.knowledge.symbol_indexer import SymbolIndexer

        symbols = []

        # Use existing SymbolIndexer to extract symbols
        indexer = SymbolIndexer()

        # Find all Rust files
        rust_files = list(crate_path.rglob("*.rs"))
        logger.debug(f"Found {len(rust_files)} Rust files in {crate_name}")

        for file_path in rust_files:
            extracted = indexer._extract_symbols_from_file(file_path)
            for sym in extracted:
                # Convert to SymbolLocation with crate prefix
                symbols.append(
                    SymbolLocation(
                        crate=crate_name,
                        version=version,
                        name=sym.name,
                        file_path=str(file_path.relative_to(crate_path.parent.parent)),
                        line=sym.line,
                        kind=sym.kind,
                        signature=sym.signature,
                    )
                )

        return symbols

    def _index_crate(self, name: str, version: str) -> CrateInfo | None:
        """Index a single crate.

        Args:
            name: Crate name
            version: Crate version

        Returns:
            CrateInfo with indexed symbols, or None if failed
        """
        logger.info(f"Indexing crate: {name} v{version}")

        crate_info = CrateInfo(name=name, version=version)

        # Find crate source
        crate_path = self._find_crate_in_registry(name, version)
        if crate_path is None:
            logger.warning(f"Could not find source for {name} v{version}")
            return None

        crate_info.path = crate_path

        # Extract symbols
        start = time.perf_counter()
        symbols = self._extract_symbols_from_crate(crate_path, name, version)
        elapsed = (time.perf_counter() - start) * 1000

        logger.info(f"  Extracted {len(symbols)} symbols from {name} in {elapsed:.0f}ms")

        # Convert to dict format
        for sym in symbols:
            crate_info.symbols.append(
                {
                    "name": sym.name,
                    "file": sym.file_path,
                    "line": sym.line,
                    "kind": sym.kind,
                    "signature": sym.signature,
                }
            )

        return crate_info

    def index_project(
        self,
        cargo_path: str | Path,
        clean: bool = False,
    ) -> dict[str, Any]:
        """Index all dependencies from a Cargo.toml file.

        Args:
            cargo_path: Path to Cargo.toml
            clean: If True, re-index all dependencies from scratch

        Returns:
            Dictionary with indexing statistics
        """
        cargo_path = Path(cargo_path)
        start = time.perf_counter()

        # Load existing index
        if not clean:
            self._load_index()

        # Parse dependencies
        dependencies = self._parse_cargo_toml(cargo_path)
        logger.info(f"Found {len(dependencies)} dependencies in {cargo_path.name}")

        indexed = 0
        skipped = 0
        errors = 0

        for name, (version, source) in sorted(dependencies.items()):
            # Skip if already indexed
            if not clean and name in self._external_index:
                logger.debug(f"Skipping {name} v{version} (already indexed)")
                skipped += 1
                continue

            # Index the crate
            crate_info = self._index_crate(name, version)
            if crate_info is None:
                errors += 1
                continue

            self._external_index[name] = crate_info

            # Build symbol lookup (skip if key is invalid)
            for sym in crate_info.symbols:
                safe_key = f"{name}::{sym['name']}"
                # Skip keys with special characters that would cause issues
                if not safe_key.isidentifier() and not all(
                    c.isalnum() or c in "_:<>" for c in safe_key
                ):
                    continue

                if safe_key not in self._symbol_lookup:
                    self._symbol_lookup[safe_key] = []

                self._symbol_lookup[safe_key].append(
                    SymbolLocation(
                        crate=name,
                        version=version,
                        name=sym["name"],
                        file_path=sym["file"],
                        line=sym["line"],
                        kind=sym["kind"],
                        signature=sym["signature"],
                    )
                )

            indexed += 1

        # Save index
        self._save_index()

        elapsed = (time.perf_counter() - start) * 1000

        result = {
            "total_dependencies": len(dependencies),
            "indexed": indexed,
            "skipped": skipped,
            "errors": errors,
            "total_symbols": sum(len(c.symbols) for c in self._external_index.values()),
            "time_ms": elapsed,
        }

        logger.info(f"Dependency indexing complete: {result}")
        return result

    def search(
        self,
        pattern: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for symbols matching a pattern.

        Args:
            pattern: Search pattern (supports * wildcards)
            limit: Maximum results to return

        Returns:
            List of matching symbols with location info
        """
        import fnmatch

        results = []

        # Handle crate::symbol pattern
        if "::" in pattern:
            parts = pattern.split("::")
            if len(parts) >= 2:
                crate_prefix = parts[0]
                symbol_pattern = "::".join(parts[1:])

                # Search within specific crate
                if crate_prefix in self._external_index:
                    crate = self._external_index[crate_prefix]
                    for sym in crate.symbols:
                        if fnmatch.fnmatch(sym["name"], symbol_pattern):
                            results.append(
                                {
                                    "crate": crate.name,
                                    "version": crate.version,
                                    "name": sym["name"],
                                    "file": sym["file"],
                                    "line": sym["line"],
                                    "kind": sym["kind"],
                                    "signature": sym["signature"],
                                }
                            )
                            if len(results) >= limit:
                                return results
                    return results

        # Search all crates
        for crate_name, crate in self._external_index.items():
            for sym in crate.symbols:
                if fnmatch.fnmatch(sym["name"], pattern):
                    results.append(
                        {
                            "crate": crate_name,
                            "version": crate.version,
                            "name": sym["name"],
                            "file": sym["file"],
                            "line": sym["line"],
                            "kind": sym["kind"],
                            "signature": sym["signature"],
                        }
                    )
                    if len(results) >= limit:
                        return results

        return results

    def search_crate(self, crate_name: str, pattern: str = "*") -> list[dict[str, Any]]:
        """Search for symbols within a specific crate.

        Args:
            crate_name: Name of the crate to search
            pattern: Symbol name pattern (default: all)

        Returns:
            List of matching symbols
        """
        import fnmatch

        if crate_name not in self._external_index:
            logger.warning(f"Crate {crate_name} not indexed")
            return []

        crate = self._external_index[crate_name]
        results = []

        for sym in crate.symbols:
            if fnmatch.fnmatch(sym["name"], pattern):
                results.append(
                    {
                        "name": sym["name"],
                        "file": sym["file"],
                        "line": sym["line"],
                        "kind": sym["kind"],
                        "signature": sym["signature"],
                    }
                )

        return results

    def get_crate_symbols(self, crate_name: str) -> list[dict[str, Any]]:
        """Get all symbols from a crate.

        Args:
            crate_name: Name of the crate

        Returns:
            List of all symbols in the crate
        """
        if crate_name not in self._external_index:
            return []

        return self._external_index[crate_name].symbols

    def get_indexed_crates(self) -> list[dict[str, Any]]:
        """Get list of all indexed crates.

        Returns:
            List of crate info dicts
        """
        return [
            {
                "name": name,
                "version": crate.version,
                "symbol_count": len(crate.symbols),
                "path": str(crate.path) if crate.path else None,
            }
            for name, crate in sorted(self._external_index.items())
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get indexing statistics.

        Returns:
            Dictionary with index statistics
        """
        return {
            "total_crates": len(self._external_index),
            "total_symbols": sum(len(c.symbols) for c in self._external_index.values()),
            "crates": self.get_indexed_crates(),
        }

    def _save_index(self) -> None:
        """Save the index to disk."""
        data = {
            "crates": {
                name: {
                    "name": crate.name,
                    "version": crate.version,
                    "path": str(crate.path) if crate.path else None,
                    "symbols": crate.symbols,
                }
                for name, crate in self._external_index.items()
            }
        }

        self._index_file.write_text(json.dumps(data, indent=2))
        logger.debug(f"Saved index to {self._index_file}")

    def _load_index(self) -> bool:
        """Load the index from disk.

        Returns:
            True if loaded successfully, False otherwise
        """
        if not self._index_file.exists():
            logger.debug(f"No existing index found at {self._index_file}")
            return False

        try:
            data = json.loads(self._index_file.read_text())

            for name, crate_data in data.get("crates", {}).items():
                self._external_index[name] = CrateInfo(
                    name=crate_data["name"],
                    version=crate_data["version"],
                    path=Path(crate_data["path"]) if crate_data.get("path") else None,
                    symbols=crate_data.get("symbols", []),
                )

            logger.info(f"Loaded {len(self._external_index)} crates from index")
            return True

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load index: {e}")
            return False

    def clear(self) -> None:
        """Clear the index."""
        self._external_index.clear()
        self._symbol_lookup.clear()

        if self._index_file.exists():
            self._index_file.unlink()

        logger.info("Index cleared")


# =============================================================================
# Convenience Functions
# =============================================================================


def index_cargo_dependencies(
    cargo_path: str | Path,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    """Index dependencies from a Cargo.toml file.

    Args:
        cargo_path: Path to Cargo.toml
        cache_dir: Directory to store indexed data

    Returns:
        Dictionary with indexing statistics
    """
    indexer = DependencyIndexer(cache_dir)
    return indexer.index_project(cargo_path)


def search_dependency(
    pattern: str,
    limit: int = 20,
    cache_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Search for a symbol in indexed dependencies.

    Args:
        pattern: Search pattern (supports * wildcards and crate::symbol format)
        limit: Maximum results
        cache_dir: Directory containing the index

    Returns:
        List of matching symbols
    """
    indexer = DependencyIndexer(cache_dir)
    indexer._load_index()  # Load existing index
    return indexer.search(pattern, limit)


def index_all_workspace(
    workspace_root: str | Path = "packages/rust/crates",
) -> dict[str, Any]:
    """Index all workspace dependencies for fast API lookup.

    Scans all Cargo.toml files in the workspace and indexes their dependencies.
    Indexed data is cached for fast subsequent queries.

    Args:
        workspace_root: Root directory containing Cargo.toml workspace members

    Returns:
        Dictionary with total crates indexed, total symbols, and time elapsed
    """
    workspace_root = Path(workspace_root)
    if not workspace_root.exists():
        workspace_root = Path(".")
        if not (workspace_root / "Cargo.toml").exists():
            return {
                "success": False,
                "error": "No workspace found",
            }

    cargo_files = list(workspace_root.rglob("Cargo.toml"))

    total_stats = {
        "total_crates": 0,
        "total_symbols": 0,
        "time_ms": 0,
        "errors": 0,
        "indexed_files": [],
    }

    start = time.perf_counter()
    indexer = DependencyIndexer()

    for cargo_path in cargo_files:
        result = indexer.index_project(cargo_path, clean=False)
        total_stats["total_crates"] += result["indexed"]
        total_stats["total_symbols"] += result["total_symbols"]
        total_stats["errors"] += result.get("errors", 0)
        if result["indexed"] > 0:
            total_stats["indexed_files"].append(str(cargo_path))

    total_stats["time_ms"] = (time.perf_counter() - start) * 1000

    return {
        "success": True,
        **total_stats,
    }


# =============================================================================
# CLI Entry Point
# =============================================================================


def main():
    """CLI interface for dependency indexing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Index Rust crate dependencies for fast API lookup"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # index command
    index_parser = subparsers.add_parser("index", help="Index dependencies from Cargo.toml")
    index_parser.add_argument(
        "cargo_path",
        nargs="?",
        default="Cargo.toml",
        help="Path to Cargo.toml (default: Cargo.toml)",
    )
    index_parser.add_argument(
        "--clean",
        action="store_true",
        help="Force full re-index",
    )

    # index-all command
    index_all_parser = subparsers.add_parser("index-all", help="Index all workspace dependencies")
    index_all_parser.add_argument(
        "--workspace",
        default="packages/rust/crates",
        help="Workspace root directory (default: packages/rust/crates)",
    )

    # search command
    search_parser = subparsers.add_parser("search", help="Search indexed dependencies")
    search_parser.add_argument("pattern", help="Search pattern")
    search_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum results (default: 10)"
    )

    # stats command
    subparsers.add_parser("stats", help="Show index statistics")

    args = parser.parse_args()

    if args.command == "index":
        result = index_cargo_dependencies(args.cargo_path)
        if result["errors"] > 0:
            print(
                f"Indexed {result['indexed']} crates ({result['total_symbols']} symbols) with {result['errors']} errors"
            )
        else:
            print(
                f"Indexed {result['indexed']} crates ({result['total_symbols']} symbols) in {result['time_ms']:.0f}ms"
            )

    elif args.command == "index-all":
        result = index_all_workspace(args.workspace)
        if result["success"]:
            print(
                f"Indexed {result['total_crates']} crates ({result['total_symbols']} symbols) in {result['time_ms']:.0f}ms"
            )
            for f in result["indexed_files"][:5]:
                print(f"  - {f}")
            if len(result["indexed_files"]) > 5:
                print(f"  ... and {len(result['indexed_files']) - 5} more")
        else:
            print(f"Error: {result['error']}")

    elif args.command == "search":
        results = search_dependency(args.pattern, limit=args.limit)
        for r in results:
            print(f"{r['kind']} {r['name']} @ {r['crate']}/{r['file']}:{r['line']}")
            print(f"  Signature: {r['signature']}")
        print(f"\n{len(results)} results")

    elif args.command == "stats":
        indexer = DependencyIndexer()
        indexer._load_index()
        stats = indexer.get_stats()
        print(f"Total crates: {stats['total_crates']}")
        print(f"Total symbols: {stats['total_symbols']}")
        for c in stats["crates"][:10]:
            print(f"  {c['name']} v{c['version']}: {c['symbol_count']} symbols")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
