"""
utils - Common utilities for MCP servers.

Phase 29: Protocol-based design with slots=True.

Modules:
- path_safety.py: Path safety checking
- file_ops.py: Safe file operations
- env.py: Environment variable utilities

Note: Logging has been moved to common.log_config (Phase 35.2)

Usage:
    from common.log_config import configure_logging, get_logger
    from mcp_core.utils import is_safe_path, read_file_safely

    configure_logging(level="INFO")
    is_safe, error = is_safe_path("path/to/file.txt")
"""

from common.log_config import configure_logging as setup_logging, get_logger
from .path_safety import is_safe_path, is_safe_command, resolve_project_path, get_relative_path, normalize_path
from .file_ops import read_file_safely, write_file_safely
from .env import load_env_from_file, get_env

__all__ = [
    # Logging (re-exported from common.log_config)
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
