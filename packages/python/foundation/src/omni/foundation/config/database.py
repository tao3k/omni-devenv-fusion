# database.py
"""
Database Path Utilities.

Provides database path management for:
- Vector databases (LanceDB)
- Checkpoint database
- Memory database (Hippocampus)

Reads configuration from settings.yaml.
"""

from pathlib import Path


def get_vector_db_path() -> Path:
    """Get the vector store base directory path.

    This is the unified directory for all LanceDB databases in the project.
    Individual stores append their own filenames:
    - Skills: get_vector_db_path() / "skills.lance"
    - Router: get_vector_db_path() / "router.lance"
    - Librarian: get_vector_db_path() / "knowledge.lance"

    Returns:
        Path to .cache/omni-vector/
    """
    from omni.foundation.config.prj import get_cache_dir

    return get_cache_dir("omni-vector")


def get_database_paths() -> dict[str, str]:
    """Get all database paths used by Omni.

    Returns a dict with database name -> absolute path.
    All paths are relative to the vector DB base directory.

    Databases:
        skills   - Main skill tools database
        router   - Router/hybrid search index
        knowledge - Knowledge base
        memory - Long-term memory/experience storage (Hippocampus)
    """
    base = get_vector_db_path()
    return {
        "skills": str(base / "skills.lance"),
        "router": str(base / "router.lance"),
        "knowledge": str(base / "knowledge.lance"),
        "memory": str(base / "memory.hippocampus.lance"),
    }


def get_database_path(name: str) -> str:
    """Get the path for a specific database.

    Args:
        name: Database name (skills, router, knowledge, memory)

    Returns:
        Absolute path to the database directory
    """
    paths = get_database_paths()
    if name not in paths:
        raise ValueError(f"Unknown database: {name}. Valid: {list(paths.keys())}")
    return paths[name]


def get_checkpoint_db_path() -> Path:
    """Get the checkpoint database path from settings.

    Reads from settings.yaml -> checkpoint.db_path
    Supports both relative (to project root) and absolute paths.

    Returns:
        Path to the LanceDB checkpoint database

    Usage:
        >>> from omni.foundation.config.database import get_checkpoint_db_path
        >>> checkpoint_path = get_checkpoint_db_path()
        >>> # Returns: /project/.cache/checkpoints.lance
    """
    from omni.foundation.config.settings import get_setting

    db_path = get_setting("checkpoint.db_path")
    if not db_path:
        from omni.foundation.config.prj import get_cache_dir

        return get_cache_dir("checkpoints.lance")

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


def get_memory_db_path() -> Path:
    """Get the memory database path (Hippocampus).

    Returns:
        Path to the LanceDB memory database in the vector store directory.

    Usage:
        >>> from omni.foundation.config.database import get_memory_db_path
        >>> memory_path = get_memory_db_path()
        >>> # Returns: /project/.cache/omni-vector/memory.hippocampus.lance
    """
    return get_vector_db_path() / "memory.hippocampus.lance"


__all__ = [
    "get_vector_db_path",
    "get_database_paths",
    "get_database_path",
    "get_checkpoint_db_path",
    "get_checkpoint_table_name",
    "get_memory_db_path",
]
