"""
lazy_cache/repomix_cache.py
Repomix-based context caching for LLM consumption.

Features:
- Caching: Stores XML in .cache/<project>/skill_<name>_repomix.xml
- Atomicity: Uses repomix.json in target directory if present
- Dynamic: Generates temp config if no repomix.json found
- XML Native: Forces XML output for optimal LLM parsing

Protocol-based design.

Note: Unlike LazyCacheBase, this is NOT a singleton. Each skill gets its own instance.

Usage:
    cache = RepomixCache(target_path=skill_dir)
    xml_context = cache.get()
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from omni.foundation.config.logging import get_logger

logger = get_logger(__name__)


class RepomixCache:
    """Pack directory as XML using repomix for LLM context.

    Features:
    - Caching: Stores XML in .cache/<project>/skill_<name>_repomix.xml
    - Atomicity: Uses repomix.json in target directory if present
    - Dynamic: Generates temp config if no repomix.json found
    - XML Native: Forces XML output for optimal LLM parsing

    Note: Unlike LazyCacheBase, this is NOT a singleton. Each skill gets its own instance.

    Usage:
        cache = RepomixCache(target_path=skill_dir)
        xml_context = cache.get()
    """

    __slots__ = (
        "_cache_dir",
        "_cached",
        "_explicit_config",
        "_ignore_patterns",
        "_loaded",
        "_output_file",
        "_repomix_bin",
        "_target_path",
    )

    def __init__(
        self,
        target_path: Path,
        config_path: Path | None = None,
        ignore_patterns: list[str] | None = None,
    ) -> None:
        """Initialize RepomixCache.

        Args:
            target_path: Directory or file to pack.
            config_path: Explicit path to repomix.json.
            ignore_patterns: Additional dynamic ignores.
        """

        self._target_path = target_path
        self._explicit_config = config_path
        self._ignore_patterns = ignore_patterns or []
        self._repomix_bin = shutil.which("repomix")

        # Determine cache directory and output file path
        from omni.foundation import prj_dirs

        skill_name = target_path.name
        self._cache_dir = prj_dirs.PRJ_CACHE()
        self._output_file = self._cache_dir / f"skill_{skill_name}_repomix.xml"

        self._cached: str | None = None
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
            logger.warning("repomix not found in PATH")
            return ""

        if not self._target_path.exists():
            logger.warning(f"Target path does not exist: {self._target_path}")
            return ""

        # Create cache directory if needed
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # Check if cached file exists - use it directly
        if self._output_file.exists():
            logger.debug(f"Using cached repomix: {self._output_file}")
            return self._output_file.read_text(encoding="utf-8")

        # Determine config to use
        config_to_use: Path | None = self._explicit_config
        local_config = self._target_path / "repomix.json"
        temp_config_file: Path | None = None

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
                logger.error(f"Failed to create temp config: {e}")
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
                logger.error(f"repomix failed: {result.stderr}")
                return ""

            # Read and return XML content from cache
            if self._output_file.exists():
                return self._output_file.read_text(encoding="utf-8")

            return ""

        except Exception as e:
            logger.error(f"RepomixCache error: {e}")
            return ""

        finally:
            # Cleanup temp config file
            if temp_config_file and Path(temp_config_file.name).exists():
                Path(temp_config_file.name).unlink(missing_ok=True)


__all__ = ["RepomixCache"]
