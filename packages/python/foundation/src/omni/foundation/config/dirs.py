# prj_dirs.py
"""
Project Directory Utilities - Centralized project directory handling.

Provides access to all PRJ_SPEC directories defined by direnv:
- PRJ_CONFIG_HOME: .config
- PRJ_RUNTIME_DIR: .run
- PRJ_CACHE_HOME: .cache
- PRJ_DATA_HOME: .data
- PRJ_PATH: .bin

Usage:
    from omni.foundation import PRJ_DIRS, PRJ_DATA, PRJ_CACHE, PRJ_CONFIG

    # Using PRJ_DIRS callable
    PRJ_DIRS.config_home / "settings.json"    # -> /project/.config/settings.json
    PRJ_DIRS.data_home / "knowledge/sessions" # -> /project/.data/knowledge/sessions
    PRJ_DIRS.cache_home / "memory"            # -> /project/.cache/memory

    # Using convenience singletons
    PRJ_DATA("knowledge", "sessions")         # -> /project/.data/knowledge/sessions
    PRJ_CACHE("memory")                       # -> /project/.cache/memory
    PRJ_CONFIG("settings.json")               # -> /project/.config/settings.json

Environment Variables (from direnv .envrc):
    PRJ_ROOT=/path/to/project
    PRJ_CONFIG_HOME=.config
    PRJ_RUNTIME_DIR=.run
    PRJ_CACHE_HOME=.cache
    PRJ_DATA_HOME=.data
    PRJ_PATH=.bin
"""

from pathlib import Path
from typing import Literal

# =============================================================================
# PRJ_SPEC Environment Variables
# =============================================================================


def _get_env(key: str, default: str) -> str:
    """Get environment variable with default."""
    import os

    return os.environ.get(key, default)


# Define PRJ_SPEC directories with env var names and defaults
_PRJ_SPECS: dict[str, tuple[str, str]] = {
    "config_home": ("PRJ_CONFIG_HOME", ".config"),
    "runtime_dir": ("PRJ_RUNTIME_DIR", ".run"),
    "cache_home": ("PRJ_CACHE_HOME", ".cache"),
    "data_home": ("PRJ_DATA_HOME", ".data"),
    "path_dir": ("PRJ_PATH", ".bin"),
}


# =============================================================================
# PrjDirs Callable Class
# =============================================================================


class _PrjDirsCallable:
    """Callable that returns project directory paths based on PRJ_SPEC env vars.

    Usage:
        PRJ_DIRS.config_home / "settings.json"   # -> /project/.config/settings.json
        PRJ_DIRS.data_home / "sessions"          # -> /project/.data/sessions
        PRJ_DIRS.cache_home / "cache.json"       # -> /project/.cache/cache.json
    """

    _cached_dirs: dict[str, Path] = {}

    def _get_dir(self, name: str) -> Path:
        """Get a project directory path by name."""
        if name in self._cached_dirs:
            return self._cached_dirs[name]

        env_key, default = _PRJ_SPECS[name]
        dir_name = _get_env(env_key, default)

        from omni.foundation.runtime.gitops import get_project_root

        project_root = get_project_root()
        dir_path = project_root / dir_name
        self._cached_dirs[name] = dir_path
        return dir_path

    def __getattr__(self, name: str) -> Path:
        """Support attribute access for directory names.

        Usage:
            PRJ_DIRS.config_home  # -> Path to .config
            PRJ_DIRS.data_home    # -> Path to .data
        """
        if name in _PRJ_SPECS:
            return self._get_dir(name)
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def __call__(
        self,
        subdir: str,
        *more_parts: str,
        category: Literal["config", "cache", "data", "runtime", "path"] = "data",
    ) -> Path:
        """Get path for a subdirectory in a specific category.

        Args:
            subdir: Subdirectory name
            *more_parts: Additional path parts
            category: Directory category (config, cache, data, runtime, path)

        Returns:
            Absolute path to the directory or file

        Usage:
            PRJ_DIRS("knowledge", "sessions")              # -> .data/knowledge/sessions
            PRJ_DIRS("knowledge", "sessions", category="data")
            PRJ_DIRS("memory", "cache.json", category="cache")
        """
        env_key, _ = _PRJ_SPECS.get(f"{category}_home", ("PRJ_DATA_HOME", ".data"))
        dir_name = _get_env(env_key, ".data")

        from omni.foundation.runtime.gitops import get_project_root

        project_root = get_project_root()
        path = project_root / dir_name / subdir
        if more_parts:
            path = path / "/".join(more_parts)
        return path

    def ensure_dir(
        self,
        subdir: str,
        *more_parts: str,
        category: Literal["config", "cache", "data", "runtime", "path"] = "data",
    ) -> Path:
        """Get path and ensure directory exists.

        Args:
            subdir: Subdirectory name
            *more_parts: Additional path parts
            category: Directory category

        Returns:
            Path to the directory (creates if not exists)

        Usage:
            PRJ_DIRS.ensure_dir("knowledge", "sessions")
            # Creates .data/knowledge/sessions/ and returns the path
        """
        path = self(subdir, *more_parts, category=category)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def clear_cache(self) -> None:
        """Clear cached directory paths (useful for testing)."""
        self._cached_dirs.clear()


# =============================================================================
# Convenience Singletons for Each Directory Type
# =============================================================================


class _PrjDirSingleton:
    """Singleton for a specific project directory type.

    Usage:
        PRJ_DATA("knowledge", "sessions")   # -> /project/.data/knowledge/sessions
        PRJ_CACHE("memory", "cache.json")   # -> /project/.cache/memory/cache.json
        PRJ_CONFIG("settings.json")         # -> /project/.config/settings.json
    """

    _category: str

    def __init__(self, category: str):
        object.__setattr__(self, "_category", category)

    def __call__(self, subdir: str = "", *more_parts: str) -> Path:
        """Get path for subdirectory in this category."""
        env_key, default = _PRJ_SPECS.get(f"{self._category}_home", ("PRJ_DATA_HOME", ".data"))
        dir_name = _get_env(env_key, default)

        from omni.foundation.runtime.gitops import get_project_root

        project_root = get_project_root()
        path = project_root / dir_name
        if subdir:
            path = path / subdir
        if more_parts:
            path = path / "/".join(more_parts)
        return path

    def __truediv__(self, other: str) -> Path:
        """Support / operator for path joining."""
        env_key, default = _PRJ_SPECS.get(f"{self._category}_home", ("PRJ_DATA_HOME", ".data"))
        dir_name = _get_env(env_key, default)

        from omni.foundation.runtime.gitops import get_project_root

        project_root = get_project_root()
        return project_root / dir_name / other

    def ensure_dir(self, subdir: str = "", *more_parts: str) -> Path:
        """Get path and ensure directory exists."""
        path = self(subdir, *more_parts)
        path.mkdir(parents=True, exist_ok=True)
        return path


# Create singleton instances
PRJ_DIRS: _PrjDirsCallable = _PrjDirsCallable()
PRJ_DATA: _PrjDirSingleton = _PrjDirSingleton("data")
PRJ_CACHE: _PrjDirSingleton = _PrjDirSingleton("cache")
PRJ_CONFIG: _PrjDirSingleton = _PrjDirSingleton("config")
PRJ_RUNTIME: _PrjDirSingleton = _PrjDirSingleton("runtime")
PRJ_PATH: _PrjDirSingleton = _PrjDirSingleton("path")
PRJ_CHECKPOINT: _PrjDirSingleton = _PrjDirSingleton("cache")  # Checkpoint uses cache dir


# =============================================================================
# API Functions
# =============================================================================


def get_prj_dir(
    category: Literal["config", "cache", "data", "runtime", "path"] = "data",
    subdir: str = "",
) -> Path:
    """Function form for getting project directory paths.

    Args:
        category: Directory category
        subdir: Optional subdirectory

    Returns:
        Absolute path to the directory
    """
    env_key, default = _PRJ_SPECS.get(f"{category}_home", ("PRJ_DATA_HOME", ".data"))
    dir_name = _get_env(env_key, default)

    from omni.foundation.runtime.gitops import get_project_root

    project_root = get_project_root()
    path = project_root / dir_name
    if subdir:
        path = path / subdir
    return path


def get_data_dir(subdir: str = "") -> Path:
    """Get data directory path (PRJ_DATA_HOME).

    Args:
        subdir: Optional subdirectory

    Returns:
        Path to .data or .data/subdir
    """
    return get_prj_dir("data", subdir)


def get_cache_dir(subdir: str = "") -> Path:
    """Get cache directory path (PRJ_CACHE_HOME).

    Args:
        subdir: Optional subdirectory

    Returns:
        Path to .cache or .cache/subdir
    """
    return get_prj_dir("cache", subdir)


def get_config_dir(subdir: str = "") -> Path:
    """Get config directory path (PRJ_CONFIG_HOME).

    Args:
        subdir: Optional subdirectory

    Returns:
        Path to .config or .config/subdir
    """
    return get_prj_dir("config", subdir)


def get_runtime_dir(subdir: str = "") -> Path:
    """Get runtime directory path (PRJ_RUNTIME_DIR).

    Args:
        subdir: Optional subdirectory

    Returns:
        Path to .run or .run/subdir
    """
    return get_prj_dir("runtime", subdir)


def get_skills_dir() -> Path:
    """Get the skills directory path.

    Uses SKILLS_DIR from omni.foundation.config.skills which reads from settings.yaml.

    Returns:
        Path to skills directory (default: assets/skills)
    """
    from omni.foundation.config.skills import SKILLS_DIR

    return SKILLS_DIR()


def get_checkpoint_db_path() -> Path:
    """Get the checkpoint database path from settings.

    Reads from settings.yaml -> checkpoint.db_path
    Supports both relative (to project root) and absolute paths.

    Returns:
        Path to the LanceDB checkpoint database

    Usage:
        >>> from omni.foundation import get_checkpoint_db_path
        >>> checkpoint_path = get_checkpoint_db_path()
        >>> # Returns: /project/.cache/checkpoints.lance
    """
    from omni.foundation.config.settings import get_setting

    db_path = get_setting("checkpoint.db_path")

    # Check if absolute path
    if Path(db_path).is_absolute():
        return Path(db_path)

    # Relative path - resolve from project root
    from omni.foundation.runtime.gitops import get_project_root

    project_root = get_project_root()
    return project_root / db_path


def get_checkpoint_table_name(workflow_type: str) -> str:
    """Get the full table name for a workflow type.

    Args:
        workflow_type: Type of workflow (e.g., "smart_commit", "research")

    Returns:
        Full table name with prefix (e.g., "checkpoint_smart_commit")
    """
    from omni.foundation.config.settings import get_setting

    prefix = get_setting("checkpoint.table_prefix")
    return f"{prefix}{workflow_type}"


def get_vector_db_path() -> Path:
    """Get the vector store base directory path.

    This is the unified directory for all LanceDB databases in the project.
    Individual stores append their own filenames:
    - Skills: get_vector_db_path() / "skills.lance"
    - Router: get_vector_db_path() / "router.lance"
    - Librarian: get_vector_db_path() / "knowledge.lance"

    NOTE: Use get_database_path() from omni.agent.cli.commands.reindex
    for centralized database path management.

    Returns:
        Path to .cache/omni-vector/

    Usage:
        >>> from omni.foundation.config.dirs import get_vector_db_path
        >>> db_dir = get_vector_db_path()
        >>> # Returns: /project/.cache/omni-vector/
        >>> # Use with: db_dir / "router.lance"
    """
    return get_cache_dir("omni-vector")


def get_checkpoints_db_path() -> Path:
    """Get the checkpoints LanceDB database path.

    Reads from settings.yaml -> checkpoint.db_path

    Returns:
        Path to the LanceDB checkpoint database

    Usage:
        >>> from omni.foundation.config.dirs import get_checkpoints_db_path
        >>> db_path = get_checkpoints_db_path()
        >>> # Returns: /project/.cache/omni-vector/checkpoints.lance
    """
    from omni.foundation.config.settings import get_setting

    db_path = get_setting("checkpoint.db_path")

    # Check if absolute path
    if Path(db_path).is_absolute():
        return Path(db_path)

    # Relative path - resolve from project root
    from omni.foundation.runtime.gitops import get_project_root

    project_root = get_project_root()
    return project_root / db_path


def get_memory_db_path() -> Path:
    """Get the memory LanceDB database path.

    Returns:
        Path to the memory database (.cache/omni-vector/memory.lance)

    Usage:
        >>> from omni.foundation.config.dirs import get_memory_db_path
        >>> db_path = get_memory_db_path()
        >>> # Returns: /project/.cache/omni-vector/memory.lance
    """
    return get_vector_db_path() / "memory.lance"


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "PRJ_CACHE",
    "PRJ_CHECKPOINT",
    "PRJ_CONFIG",
    "PRJ_DATA",
    "PRJ_DIRS",
    "PRJ_PATH",
    "PRJ_RUNTIME",
    "get_cache_dir",
    "get_checkpoints_db_path",
    "get_vector_db_path",
    "get_checkpoint_table_name",
    "get_config_dir",
    "get_data_dir",
    "get_memory_db_path",
    "get_prj_dir",
    "get_runtime_dir",
    "get_skills_dir",
]
