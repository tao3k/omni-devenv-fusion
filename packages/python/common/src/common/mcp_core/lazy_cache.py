# mcp-core/lazy_cache.py
"""
Lazy Loading Singleton Cache - Memory-efficient caching for protocol and config data.

This module provides a base class for implementing lazy-loading singleton caches,
which are ideal for:
- Protocol rules (gitops.md, testing-workflows.md)
- Configuration files (cog.toml, .conform.yaml)
- Writing style guidelines (agent/writing-style/*.md)
- Language-specific standards (agent/standards/lang-*.md)

Uses GitOps via common.mcp_core.gitops for path detection.
References configured in agent/knowledge/references.yaml.

Features:
- Singleton pattern: Only one instance per cache type
- Lazy loading: Load on first access, not at import time
- Thread-safe: Safe for concurrent access
- Easy subclassing: Override _load() to implement custom loading logic
- Hot reload: reload() method to refresh cache

Usage:
    from mcp_core.lazy_cache import LazyCache

    class GitWorkflowCache(LazyCache[dict]):
        def _load(self) -> dict:
            # Load and return data from file
            return {"protocol": "stop_and_ask"}

    # First access triggers load
    cache = GitWorkflowCache()
    protocol = cache.get("protocol")  # Loaded here

    # Subsequent accesses use cached value
    protocol = cache.get("protocol")  # Cached!
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generic, TypeVar, Callable, Optional

T = TypeVar("T")

# Project root detection using GitOps
from common.gitops import get_project_root
from common.settings import get_setting

_PROJECT_ROOT: Path | None = None


def _get_project_root() -> Path:
    """Get the project root directory (uses GitOps)."""
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        _PROJECT_ROOT = get_project_root()
    return _PROJECT_ROOT


class LazyCache(ABC, Generic[T]):
    """Abstract base class for lazy-loading singleton caches.

    Subclasses must implement _load() to define how data is loaded.
    The cache uses singleton pattern - only one instance exists.

    Example:
        class WritingStyleCache(LazyCache[dict]):
            @property
            def _file_path(self) -> Path:
                return get_project_root() / get_setting("assets.writing_style_dir") / "concise.md"

            def _load(self) -> dict:
                # Parse writing style guidelines from file
                content = self._file_path.read_text()
                return self._parse(content)

        cache = WritingStyleCache()
        guidelines = cache.get()  # Auto-loaded on first call
    """

    _instance: Optional["LazyCache[T]"] = None
    _instance_lock = threading.Lock()
    _loaded: bool = False

    def __new__(cls, eager: bool = False) -> "LazyCache[T]":
        """Create singleton instance with optional eager loading.

        Args:
            eager: If True, load cache immediately on creation.

        Returns:
            Singleton instance of the cache.
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._data: T | None = None

                    if eager:
                        cls._instance._ensure_loaded()

        return cls._instance

    def __init__(self, eager: bool = False) -> None:
        """Initialize cache.

        Note:
            Singleton pattern ensures __init__ only runs once per class.
        """
        pass

    def _ensure_loaded(self) -> T:
        """Ensure data is loaded, thread-safe with double-check locking.

        Returns:
            The loaded data.
        """
        if not self._loaded:
            with self._instance_lock:
                if not self._loaded:
                    self._data = self._load()
                    self._loaded = True
        return self._data  # type: ignore[return-value]

    @abstractmethod
    def _load(self) -> T:
        """Load and return cached data.

        Override this method in subclasses to implement custom loading logic.
        This is called exactly once - on first access.

        Returns:
            The data to cache and return on subsequent get() calls.
        """
        ...

    def get(self) -> T:
        """Get cached data, loading if necessary.

        Returns:
            The cached data.
        """
        return self._ensure_loaded()

    def reload(self) -> T:
        """Force reload of cached data.

        Use this to refresh cache after source files change.

        Returns:
            The newly loaded data.
        """
        with self._instance_lock:
            self._data = self._load()
            self._loaded = True
        return self._data  # type: ignore[return-value]

    @property
    def is_loaded(self) -> bool:
        """Check if cache has been loaded.

        Returns:
            True if cache is loaded, False otherwise.
        """
        return self._loaded

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance.

        Use with caution - this clears the cache and creates a new instance.
        Primarily for testing.
        """
        with cls._instance_lock:
            cls._instance = None
            cls._loaded = False


class FileCache(LazyCache[str]):
    """Lazy cache for loading and caching file contents.

    Example:
        cache = FileCache(get_project_root() / get_setting("assets.howto_dir") / "gitops.md")
        content = cache.get()  # Loaded once, cached forever
    """

    def __init__(self, file_path: Path, eager: bool = False) -> None:
        """Initialize file cache.

        Args:
            file_path: Path to the file to cache.
            eager: If True, load file immediately.
        """
        self._file_path = file_path
        super().__init__(eager=eager)

    def _load(self) -> str:
        """Load file contents.

        Returns:
            File contents as string, or empty string if file doesn't exist.
        """
        if not self._file_path.exists():
            return ""
        return self._file_path.read_text(encoding="utf-8")

    @property
    def content(self) -> str:
        """Get file content.

        Returns:
            Cached file content.
        """
        return self.get()


class MarkdownCache(LazyCache[dict[str, Any]]):
    """Lazy cache for parsing markdown files into structured data.

    Extracts title, content, and sections from markdown files.

    Example:
        cache = MarkdownCache(get_project_root() / get_setting("assets.howto_dir") / "gitops.md")
        data = cache.get()  # {"title": "...", "content": "...", "sections": {...}}
    """

    def __init__(self, file_path: Path, eager: bool = False) -> None:
        """Initialize markdown cache.

        Args:
            file_path: Path to the markdown file.
            eager: If True, parse file immediately.
        """
        self._file_path = file_path
        super().__init__(eager=eager)

    def _load(self) -> dict[str, Any]:
        """Parse markdown file into structured data.

        Returns:
            Dictionary with title, content, and sections.
        """
        if not self._file_path.exists():
            return {"title": "", "content": "", "sections": {}}

        content = self._file_path.read_text(encoding="utf-8")

        # Extract title (first H1)
        title_match = re.match(r"^#\s+(.+)$", content.strip(), re.MULTILINE)
        title = title_match.group(1) if title_match else ""

        # Extract sections (H2 headers)
        sections: dict[str, str] = {}
        h2_pattern = r"^##\s+(.+)$"
        h2_matches = list(re.finditer(h2_pattern, content, re.MULTILINE))

        for i, match in enumerate(h2_matches):
            section_name = match.group(1).strip()
            start = match.end()
            end = h2_matches[i + 1].start() if i + 1 < len(h2_matches) else len(content)
            sections[section_name] = content[start:end].strip()

        return {"title": title, "content": content, "sections": sections}

    @property
    def title(self) -> str:
        """Get markdown title.

        Returns:
            The title from the markdown file.
        """
        return self.get().get("title", "")

    @property
    def sections(self) -> dict[str, str]:
        """Get markdown sections.

        Returns:
            Dictionary of section names to content.
        """
        return self.get().get("sections", {})


class ConfigCache(LazyCache[dict[str, Any]]):
    """Lazy cache for configuration files (TOML, YAML, JSON).

    Automatically detects file type and parses accordingly.

    Example:
        cache = ConfigCache(get_project_root() / "cog.toml")
        config = cache.get()  # {"scopes": ["nix", "mcp", ...]}
    """

    def __init__(self, file_path: Path, eager: bool = False) -> None:
        """Initialize config cache.

        Args:
            file_path: Path to the config file.
            eager: If True, parse file immediately.
        """
        self._file_path = file_path
        super().__init__(eager=eager)

    def _load(self) -> dict[str, Any]:
        """Parse config file based on extension.

        Returns:
            Parsed configuration as dictionary.
        """
        if not self._file_path.exists():
            return {}

        content = self._file_path.read_text(encoding="utf-8")
        suffix = self._file_path.suffix.lower()

        # Handle TOML files
        if suffix == ".toml":
            try:
                import tomllib

                with open(self._file_path, "rb") as f:
                    return tomllib.load(f)
            except ImportError:
                import tomli

                with open(self._file_path, "rb") as f:
                    return tomli.load(f)

        # Handle JSON files
        if suffix == ".json":
            import json

            return json.loads(content)

        # Handle YAML files
        if suffix in (".yaml", ".yml"):
            try:
                import yaml

                return yaml.safe_load(content) or {}
            except ImportError:
                # Fallback: simple key-value parsing
                result: dict[str, str] = {}
                for line in content.split("\n"):
                    if ":" in line and not line.strip().startswith("#"):
                        key, value = line.split(":", 1)
                        result[key.strip()] = value.strip()
                return result

        # Handle .conform.yaml (special case for commit types)
        if suffix == ".conform.yaml":
            result: dict[str, Any] = {"types": []}
            found_types = re.findall(r"-\s+type:\s+([a-zA-Z0-9]+)", content)
            if found_types:
                result["types"] = list(set(found_types))
            return result

        return {}


class CompositeCache(LazyCache[dict[str, Any]]):
    """Cache that merges data from multiple sources.

    Useful for aggregating configs from multiple files with fallbacks.

    Example:
        cache = CompositeCache([
            ConfigCache(get_project_root() / "cog.toml"),
            MarkdownCache(get_project_root() / get_setting("assets.howto_dir") / "gitops.md"),
        ])
        data = cache.get()  # Merged from all sources
    """

    def __init__(
        self,
        sources: list[LazyCache[Any]],
        merger: Callable[[list[dict[str, Any]]], dict[str, Any]] | None = None,
        eager: bool = False,
    ) -> None:
        """Initialize composite cache.

        Args:
            sources: List of cache sources to merge.
            merger: Optional function to merge results.
            eager: If True, load all sources immediately.
        """
        self._sources = sources
        self._merger = merger or self._default_merger
        super().__init__(eager=eager)

    def _default_merger(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Merge results, later sources override earlier ones.

        Args:
            results: List of dictionaries to merge.

        Returns:
            Merged dictionary.
        """
        merged: dict[str, Any] = {}
        for result in results:
            merged.update(result)
        return merged

    def _load(self) -> dict[str, Any]:
        """Load and merge data from all sources.

        Returns:
            Merged dictionary from all sources.
        """
        results: list[dict[str, Any]] = []
        for source in self._sources:
            data = source.get()
            if data:
                results.append(data)
        return self._merger(results)


class RepomixCache:
    """Pack directory as XML using repomix for LLM context.

    Features:
    - Caching: Stores XML in .cache/<project>/skill_<name>_repomix.xml
    - Atomicity: Uses repomix.json in target directory if present.
    - Dynamic: Generates temp config if no repomix.json found.
    - XML Native: Forces XML output for optimal LLM parsing.

    Note: Unlike LazyCache, this is NOT a singleton. Each skill gets its own instance.

    Usage:
        cache = RepomixCache(target_path=skill_dir)
        xml_context = cache.get()
    """

    logger = logging.getLogger(__name__)

    def __init__(
        self,
        target_path: Path,
        config_path: Optional[Path] = None,
        ignore_patterns: Optional[list[str]] = None,
    ) -> None:
        """Initialize RepomixCache.

        Args:
            target_path: Directory or file to pack.
            config_path: Explicit path to repomix.json.
            ignore_patterns: Additional dynamic ignores.
        """
        from common.gitops import get_project_root

        self._target_path = target_path
        self._explicit_config = config_path
        self._ignore_patterns = ignore_patterns or []
        self._repomix_bin = shutil.which("repomix")

        # Determine cache directory and output file path
        project_root = get_project_root()
        project_name = project_root.name
        skill_name = target_path.name

        self._cache_dir = project_root / ".cache" / project_name
        self._output_file = self._cache_dir / f"skill_{skill_name}_repomix.xml"

        self._cached: Optional[str] = None
        self._loaded = False

    def get(self) -> str:
        """Get XML content, loading if necessary.

        Returns:
            XML content from repomix, or empty string on error.
        """
        if not self._loaded:
            self._cached = self._load()
            self._loaded = True
        return self._cached or ""

    def reload(self) -> str:
        """Force reload of cached data.

        Returns:
            Newly loaded XML content.
        """
        self._cached = self._load()
        self._loaded = True
        return self._cached or ""

    def _load(self) -> str:
        """Execute repomix and return XML content.

        Returns:
            XML content from repomix, or empty string on error.
        """
        if not self._repomix_bin:
            self.logger.warning("repomix not found in PATH")
            return ""

        if not self._target_path.exists():
            self.logger.warning(f"Target path does not exist: {self._target_path}")
            return ""

        # Create cache directory if needed
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # Check if cached file exists - use it directly
        if self._output_file.exists():
            self.logger.debug(f"Using cached repomix: {self._output_file}")
            return self._output_file.read_text(encoding="utf-8")

        # Determine config to use
        config_to_use: Optional[Path] = self._explicit_config
        local_config = self._target_path / "repomix.json"
        temp_config_file: Optional[Path] = None

        # Check for local repomix.json if no explicit config
        if not config_to_use and local_config.exists():
            config_to_use = local_config

        # Generate dynamic config if no config found
        if not config_to_use:
            default_config = {
                "output": {
                    "style": "xml",
                    "fileSummary": True,
                    "removeComments": False,
                },
                "include": [
                    "**/*.py",
                    "**/*.md",
                    "**/*.json",
                    "**/*.yaml",
                    "**/*.yml",
                    "Justfile",
                    "Dockerfile",
                    "Makefile",
                ],
                "ignore": {
                    "patterns": [
                        "**/__pycache__/**",
                        "**/*.pyc",
                        "**/.git/**",
                        "**/.gitignore",
                        "**/node_modules/**",
                        "**/venv/**",
                        ".env*",
                        "uv.lock",
                        "package-lock.json",
                        "*.egg-info/**",
                        ".pytest_cache/**",
                        ".hypothesis/**",
                    ],
                    "characters": self._ignore_patterns,
                },
            }

            try:
                temp_config_file = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", delete=False
                )
                json.dump(default_config, temp_config_file)
                temp_config_file.close()
                config_to_use = Path(temp_config_file.name)
            except Exception as e:
                self.logger.error(f"Failed to create temp config: {e}")
                return ""

        try:
            # Build command with --output to cache file
            cmd = [
                self._repomix_bin,
                "--config",
                str(config_to_use),
                "--style",
                "xml",
                "--output",
                str(self._output_file),
                str(self._target_path),
            ]

            # Execute
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                self.logger.error(f"repomix failed: {result.stderr}")
                return ""

            # Read and return XML content from cache
            if self._output_file.exists():
                return self._output_file.read_text(encoding="utf-8")

            return ""

        except Exception as e:
            self.logger.error(f"RepomixCache error: {e}")
            return ""

        finally:
            # Cleanup temp config file
            if temp_config_file and Path(temp_config_file.name).exists():
                Path(temp_config_file.name).unlink(missing_ok=True)
