"""
utils - Common utilities for MCP servers.

Phase 29: Protocol-based design with slots=True.

Modules:
- logging.py: Structured logging setup
- path_safety.py: Path safety checking
- file_ops.py: Safe file operations
- env.py: Environment variable utilities

Usage:
    from mcp_core.utils import setup_logging, is_safe_path, read_file_safely

    log = setup_logging(level="INFO")
    is_safe, error = is_safe_path("path/to/file.txt")
"""

from .logging import setup_logging, get_logger
from .path_safety import is_safe_path, is_safe_command
from .file_ops import read_file_safely, write_file_safely
from .env import load_env_from_file, get_env

__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    # Path safety
    "is_safe_path",
    "is_safe_command",
    # File operations
    "read_file_safely",
    "write_file_safely",
    # Environment
    "load_env_from_file",
    "get_env",
]
