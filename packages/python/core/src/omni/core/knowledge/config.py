"""Knowledge Configuration - Load settings from references.yaml."""

from pathlib import Path
from typing import Any

import yaml


class KnowledgeConfig:
    """Configuration for Project Librarian loaded from references.yaml."""

    def __init__(self, config_path: Path | None = None):
        """Initialize configuration.

        Args:
            config_path: Path to references.yaml (auto-detected if None)
        """
        self._config: dict[str, Any] = {}
        self._config_path = config_path
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from references.yaml."""
        if self._config_path is None:
            # Auto-detect: look for references.yaml in common locations
            search_paths = [
                Path.cwd() / "assets" / "references.yaml",
                Path(__file__).parent.parent.parent.parent / "assets" / "references.yaml",
            ]
            for path in search_paths:
                if path.exists():
                    self._config_path = path
                    break

        if self._config_path and self._config_path.exists():
            with open(self._config_path, "r") as f:
                self._config = yaml.safe_load(f) or {}

    @property
    def knowledge_dirs(self) -> list[dict[str, str]]:
        """Get knowledge directories from config."""
        return self._config.get("knowledge_dirs", [])

    @property
    def ast_extensions(self) -> dict[str, str]:
        """Get supported file extensions for AST chunking (code files only)."""
        return {
            ".py": "python",
            ".rs": "rust",
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
            ".java": "java",
        }

    @property
    def markdown_extensions(self) -> dict[str, str]:
        """Get supported file extensions for markdown (text chunking)."""
        return {
            ".md": "markdown",
            ".markdown": "markdown",
        }

    @property
    def supported_extensions(self) -> dict[str, str]:
        """Get ALL supported file extensions for knowledge indexing."""
        return {**self.ast_extensions, **self.markdown_extensions}

    @property
    def skip_dirs(self) -> set[str]:
        """Get directories to skip."""
        return {
            "node_modules",
            ".git",
            "__pycache__",
            ".pytest_cache",
            "target",
            "build",
            ".gradle",
            "vendor",
            ".venv",
            "venv",
            ".cache",
            "dist",
            "out",
            ".idea",
            ".vscode",
        }

    @property
    def max_file_size(self) -> int:
        """Get maximum file size to process (bytes)."""
        return 1024 * 1024  # 1MB

    @property
    def ast_patterns(self) -> dict[str, list[str]]:
        """Get language-specific AST patterns for ast-grep."""
        return {
            "python": ["def $NAME", "class $NAME"],
            "rust": ["pub fn $NAME", "pub struct $NAME", "impl $NAME"],
            "javascript": ["function $NAME", "class $NAME", "const $NAME ="],
            "typescript": ["function $NAME", "class $NAME", "const $NAME ="],
            "go": ["func $NAME", "type $NAME struct"],
            "java": ["public $NAME", "class $NAME"],
        }

    def get_knowledge_paths(self, project_root: Path) -> list[Path]:
        """Get actual paths to knowledge directories.

        Args:
            project_root: Project root directory

        Returns:
            List of Path objects for knowledge directories
        """
        paths = []
        for entry in self.knowledge_dirs:
            path_str = entry.get("path", "")
            if path_str:
                path = project_root / path_str
                if path.exists():
                    paths.append(path)
        return paths

    def to_dict(self) -> dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            "knowledge_dirs": self.knowledge_dirs,
            "ast_extensions": self.ast_extensions,
            "skip_dirs": list(self.skip_dirs),
            "max_file_size": self.max_file_size,
            "ast_patterns": self.ast_patterns,
        }


# Singleton instance
_config: KnowledgeConfig | None = None


def get_knowledge_config(config_path: Path | None = None) -> KnowledgeConfig:
    """Get the knowledge configuration singleton."""
    global _config
    if _config is None or config_path is not None:
        _config = KnowledgeConfig(config_path)
    return _config


def reset_config() -> None:
    """Reset configuration singleton (for testing)."""
    global _config
    _config = None
