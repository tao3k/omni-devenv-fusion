# mcp-core/utils.py
"""
Common Utilities Module

Provides shared utilities for both orchestrator.py and coder.py servers.

Features:
- Logging setup with structlog
- Path safety checking
- Environment variable loading
- Common helper functions
"""
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import structlog

# =============================================================================
# Logging Setup
# =============================================================================

def setup_logging(
    level: str = "INFO",
    log_format: str = "json",
    server_name: str = "mcp",
) -> logging.Logger:
    """
    Configure structured logging for MCP servers.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_format: Format type - "json" for JSON logs, "console" for pretty print
        server_name: Server identifier for log context

    Returns:
        Configured logger instance
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    if log_format == "json":
        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
            cache_logger_on_first_use=False,
        )
    else:
        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
            cache_logger_on_first_use=False,
        )

    log = structlog.get_logger(server_name)
    log.info("logging.initialized", level=log_level, format=log_format)
    return log


def get_logger(name: str = "mcp") -> structlog.BoundLogger:
    """
    Get a logger instance.

    Args:
        name: Logger name (will be prefixed with "mcp.")

    Returns:
        BoundLogger instance
    """
    return structlog.get_logger(f"mcp.{name}")


# =============================================================================
# Decision Logging (for MCP tool audit trail)
# =============================================================================

def log_decision(event: str, payload: Dict[str, Any], logger: structlog.BoundLogger = None) -> None:
    """
    Log a decision/event with structured payload.

    This provides a consistent audit trail across both servers.

    Args:
        event: Event type (e.g., "read_file.request", "execution.complete")
        payload: Event data
        logger: Optional logger instance
    """
    if logger is None:
        logger = get_logger("decision")

    logger.info(event, **payload)


# =============================================================================
# Path Safety Utilities
# =============================================================================

def is_safe_path(
    path: str,
    project_root: Path = None,
    blocked_dirs: set = None,
    allow_hidden: bool = True,
    allowed_hidden_files: set = None,
) -> tuple[bool, str]:
    """
    Check if a path is safe to access within the project.

    Args:
        path: Path to check
        project_root: Project root directory (defaults to cwd)
        blocked_dirs: Set of blocked directory prefixes
        allow_hidden: Whether to allow hidden files
        allowed_hidden_files: Set of allowed hidden filenames (e.g., {".gitignore"})

    Returns:
        Tuple of (is_safe, error_message)
    """
    if project_root is None:
        project_root = Path.cwd()

    if blocked_dirs is None:
        blocked_dirs = {"/etc/", "/usr/", "/bin/", "/sbin/", "/boot/", "/lib/", "/lib64/"}

    if allowed_hidden_files is None:
        allowed_hidden_files = set()

    # Check for absolute paths
    if path.startswith("/"):
        return False, "Absolute paths are not allowed."

    # Check for path traversal
    if ".." in path:
        return False, "Parent directory traversal is not allowed."

    # Check hidden files
    filename = Path(path).name
    if filename.startswith("."):
        if not allow_hidden:
            if filename not in allowed_hidden_files:
                return False, f"Hidden file '{filename}' is not allowed."

    # Check for blocked directories
    for blocked in blocked_dirs:
        if path.startswith(blocked):
            return False, f"Blocked path: {blocked}"

    # Resolve and check if within project
    try:
        full_path = (project_root / path).resolve()
        if not str(full_path).startswith(str(project_root.resolve())):
            return False, "Path is outside the project directory"
    except Exception as e:
        return False, f"Error resolving path: {e}"

    return True, ""


def is_safe_command(command: str, allowed_commands: Dict[str, list] = None) -> tuple[bool, str]:
    """
    Check if a command is allowed.

    Args:
        command: Command to check
        allowed_commands: Dict of allowed commands

    Returns:
        Tuple of (is_safe, error_message)
    """
    if allowed_commands is None:
        allowed_commands = {}

    if not allowed_commands:
        # Default: only allow well-known safe commands
        allowed_commands = {
            "just": [],
            "nix": [],
            "git": [],
            "echo": [],
            "cat": [],
            "head": [],
            "tail": [],
        }

    if command not in allowed_commands:
        return False, f"Command '{command}' is not in the whitelist"

    return True, ""


# =============================================================================
# Environment Variable Loading
# =============================================================================

def load_env_from_file(
    config_key: str = None,
    env_key: str = None,
    config_file: str = None,
) -> Dict[str, str]:
    """
    Load environment variables from a JSON config file.

    Supports both flat structure and nested mcpServers structure.

    Args:
        config_key: Config key to extract (e.g., "orchestrator", "coder")
        env_key: Environment variable name for config file path
        config_file: Explicit config file path

    Returns:
        Dict of environment variables
    """
    if config_file is None:
        config_file = env_key or os.environ.get("MCP_CONFIG_FILE", ".mcp.json")

    if not os.path.exists(config_file):
        return {}

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    # Handle flat config or nested mcpServers config
    if config_key and isinstance(data.get("mcpServers"), dict):
        server_config = data["mcpServers"].get(config_key, {})
        env_vars = server_config.get("env", {}) if isinstance(server_config, dict) else {}
        flat_env = data if isinstance(data, dict) else {}
    else:
        env_vars = data if isinstance(data, dict) else {}
        flat_env = data if isinstance(data, dict) else {}

    # Merge flat env with server-specific env (server config takes precedence)
    merged: Dict[str, str] = {}
    for source in (flat_env, env_vars):
        if isinstance(source, dict):
            for key, value in source.items():
                if isinstance(value, str):
                    merged[key] = value

    return merged


def get_env(key: str, env_vars: Dict[str, str] = None, default: str = None) -> str:
    """
    Get environment variable with fallback chain.

    Args:
        key: Environment variable key
        env_vars: Pre-loaded env vars dict
        default: Default value if not found

    Returns:
        Environment variable value or default
    """
    if env_vars is None:
        env_vars = {}

    return env_vars.get(key) or os.environ.get(key) or default


# =============================================================================
# File Operations
# =============================================================================

def read_file_safely(path: str, max_size: int = 100 * 1024, project_root: Path = None) -> tuple[bool, str]:
    """
    Safely read a file within project boundaries.

    Args:
        path: File path relative to project root
        max_size: Maximum file size in bytes
        project_root: Project root directory

    Returns:
        Tuple of (success, content_or_error)
    """
    is_safe, error_msg = is_safe_path(path, project_root)
    if not is_safe:
        return False, f"Error: {error_msg}"

    if project_root is None:
        project_root = Path.cwd()

    full_path = project_root / path

    if not full_path.exists():
        return False, f"Error: File '{path}' does not exist"
    if not full_path.is_file():
        return False, f"Error: '{path}' is not a file"
    if full_path.stat().st_size > max_size:
        return False, f"Error: File '{path}' is too large (> {max_size // 1024}KB)"

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        return True, content
    except UnicodeDecodeError:
        return False, f"Error: Cannot read '{path}' - not a text file"
    except Exception as e:
        return False, f"Error reading file: {e}"


def write_file_safely(
    path: str,
    content: str,
    project_root: Path = None,
    create_backup: bool = True,
) -> tuple[bool, str]:
    """
    Safely write a file within project boundaries.

    Args:
        path: File path relative to project root
        content: Content to write
        project_root: Project root directory
        create_backup: Whether to create .bak backup

    Returns:
        Tuple of (success, message)
    """
    import shutil
    from datetime import datetime

    is_safe, error_msg = is_safe_path(path, project_root)
    if not is_safe:
        return False, f"Error: {error_msg}"

    if project_root is None:
        project_root = Path.cwd()

    full_path = project_root / path

    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"Error creating directory: {e}"

    # Create backup if file exists
    backup_info = ""
    if full_path.exists() and create_backup:
        backup_path = full_path.with_suffix(full_path.suffix + ".bak")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_backup = full_path.with_suffix(f"{full_path.suffix}.{timestamp}.bak")
        shutil.copy2(full_path, final_backup)
        backup_info = f" (backup: {final_backup.name})"

    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True, f"Successfully wrote {len(content)} bytes to '{path}'{backup_info}"
    except Exception as e:
        return False, f"Error writing file: {e}"


# =============================================================================
# Async Helpers
# =============================================================================

async def run_subprocess(
    command: str,
    args: list = None,
    timeout: int = 60,
    cwd: str = None,
) -> tuple[int, str, str]:
    """
    Simple subprocess runner with timeout.

    Args:
        command: Command to run
        args: Command arguments
        timeout: Timeout in seconds
        cwd: Working directory

    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    import asyncio

    if args is None:
        args = []

    try:
        process = await asyncio.create_subprocess_exec(
            command,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd or str(Path.cwd()),
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return (process.returncode, stdout.decode("utf-8"), stderr.decode("utf-8"))

    except asyncio.TimeoutExpired:
        return (-1, "", f"Timed out after {timeout}s")
    except FileNotFoundError:
        return (-1, "", f"Command '{command}' not found")
    except Exception as e:
        return (-1, "", str(e))
