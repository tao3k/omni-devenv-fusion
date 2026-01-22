"""
utils - Common utilities for MCP servers.

Protocol-based design with slots=True.

Modules:
- path_safety.py: Path safety checking
- file_ops.py: Safe file operations
- env.py: Environment variable utilities

Note: Logging has been moved to common.log_config

Usage:
    from omni.foundation.config.logging import configure_logging, get_logger
    from mcp_core.utils import is_safe_path, read_file_safely

    configure_logging(level="INFO")
    is_safe, error = is_safe_path("path/to/file.txt")
"""

from omni.foundation.config.logging import configure_logging as setup_logging
from omni.foundation.config.logging import get_logger

from .env import get_env, load_env_from_file
from .file_ops import read_file_safely, write_file_safely
from .path_safety import (
    get_relative_path,
    is_safe_command,
    is_safe_path,
    normalize_path,
    resolve_project_path,
)

__all__ = [
    # Logging (re-exported from omni.foundation.log_config)
    "setup_logging",
    "get_logger",
    # Path safety
    "is_safe_path",
    "is_safe_command",
    "resolve_project_path",
    "get_relative_path",
    "normalize_path",
    # File operations
    "read_file_safely",
    "write_file_safely",
    # Environment
    "load_env_from_file",
    "get_env",
]
