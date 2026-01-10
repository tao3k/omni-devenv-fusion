# mcp-core - Shared library for omni-dev-fusion MCP servers
"""
Shared library providing common functionality for orchestrator.py and coder.py.

Phase 31: Optimized architecture with Protocol-based design.

Modules:
- protocols.py: Protocol definitions for type-safe, testable code
- lazy_cache/: Lazy-loading singleton caches for protocols and configs
- utils/: Common utilities (logging, path checking)
- context/: Project-specific coding context framework
- inference/: LLM inference client
- memory/: Project memory persistence
- api/: API key management
- instructions/: Eager-loaded project instructions
- settings: Common settings (fast import from common.settings)
- execution: Moved to assets/skills/terminal/tools.py (Trinity Architecture)

Usage:
    # Protocol-based design (for testing)
    from mcp_core.protocols import ISafeExecutor, IInferenceClient

    # Execution now via terminal skill (Trinity Architecture):
    # @omni("terminal.execute_command", {"command": "ls", "args": ["-la"]})

    # From modular subpackages
    from mcp_core.lazy_cache import FileCache, MarkdownCache, ConfigCache, RepomixCache
    from common.config.settings import Settings, get_setting, get_commit_types  # Fast import
    from mcp_core.utils import setup_logging, is_safe_path
    from mcp_core.context import get_project_context, ProjectContext, ContextRegistry
    from mcp_core.inference import InferenceClient, PERSONAS, build_persona_prompt
    from mcp_core.memory import ProjectMemory
    from mcp_core.api import get_anthropic_api_key
    from mcp_core.instructions import get_instructions

    # For project root detection (faster):
    from common.gitops import get_project_root
"""

from __future__ import annotations

from typing import Any

__version__ = "2.0.0"

# =============================================================================
# Protocols (Phase 29)
# =============================================================================

from .protocols import (
    # Type aliases (import directly, not as strings)
    ContextData,
    CacheValue,
    ConfigValue,
    # Lazy Cache Protocols
    ILazyCache,
    IFileCache,
    IConfigCache,
    # Settings Protocols
    ISettings,
    # Execution Protocols
    ISafeExecutor,
    # Inference Protocols
    IInferenceClient,
    # Context Protocols
    IProjectContext,
    IContextRegistry,
    # Base Dataclasses
    ExecutionResult,
    InferenceResult,
    CacheEntry,
    PathSafetyResult,
    SettingsEntry,
)

# =============================================================================
# Lazy Cache (backward compatible exports)
# =============================================================================

from .lazy_cache import (
    LazyCacheBase as LazyCache,  # Backward compat alias
    FileCache,
    MarkdownCache,
    ConfigCache,
    RepomixCache,
)

# Re-export CompositeCache if it exists in base module
try:
    from .lazy_cache.base import CompositeCache  # type: ignore
    from .lazy_cache.base import CompositeCache as CompositeCacheDirect

    CompositeCache = CompositeCacheDirect
    del CompositeCacheDirect
except ImportError:
    pass

# =============================================================================
# Execution - REMOVED (now handled by assets/skills/terminal/tools.py)
# The ISafeExecutor protocol remains for type hints, but implementation
# is provided by the terminal skill via Swarm Engine.
# =============================================================================

# =============================================================================
# Settings (import from common.config for faster imports)
# =============================================================================

from common.config.settings import (
    Settings,
    get_setting,
    get_config_path,
    has_setting,
    list_setting_sections,
)

from common.config.directory import (
    set_conf_dir,
    get_conf_dir,
)

from common.config.commits import (
    get_commit_types,
    get_commit_scopes,
    get_commit_protocol,
)

# =============================================================================
# Utils
# =============================================================================

from .utils import (
    setup_logging,
    get_logger,
    is_safe_path,
    is_safe_command,
    read_file_safely,
    write_file_safely,
    load_env_from_file,
    get_env,
)

# Keep backward compatibility for log_decision and run_subprocess
from common.log_config import get_logger as _get_logger


def log_decision(event: str, payload: dict[str, Any], logger=None) -> None:
    """Log a decision/event with structured payload."""
    if logger is None:
        logger = _get_logger("decision")
    logger.info(event, **payload)


async def run_subprocess(
    command: str,
    args: list = None,
    timeout: int = 60,
    cwd: str = None,
) -> tuple[int, str, str]:
    """Simple subprocess runner with timeout."""
    import asyncio
    from pathlib import Path

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


# =============================================================================
# Context
# =============================================================================

from .context import (
    ProjectContext,
    ContextRegistry,
    get_project_context,
    get_all_project_contexts,
    list_project_languages,
    has_project_context,
    register_project_context,
    initialize_project_contexts,
    PythonContext,
    NixContext,
)

# =============================================================================
# Inference (keep original imports)
# =============================================================================

from .inference import (
    InferenceClient,
    PERSONAS,
    build_persona_prompt,
    _load_api_key_from_config,
    DEFAULT_MODEL,
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_TOKENS,
)

# =============================================================================
# Memory (keep original imports)
# =============================================================================

from .memory import (
    ProjectMemory,
)

# =============================================================================
# Instructions (keep original imports)
# =============================================================================

from .instructions import (
    get_instructions,
    get_instruction,
    get_all_instructions_merged,
    list_instruction_names,
    reload_instructions,
)

# =============================================================================
# API Key (keep original imports)
# =============================================================================

from .api import (
    get_anthropic_api_key,
    get_api_key,
    ensure_api_key,
)

# =============================================================================
# All Exports
# =============================================================================

__all__ = [
    # Version
    "__version__",
    # Protocols
    "ContextData",
    "CacheValue",
    "ConfigValue",
    "ILazyCache",
    "IFileCache",
    "IConfigCache",
    "ISettings",
    "ISafeExecutor",
    "IInferenceClient",
    "IProjectContext",
    "IContextRegistry",
    "ExecutionResult",
    "InferenceResult",
    "CacheEntry",
    "PathSafetyResult",
    "SettingsEntry",
    # Lazy Cache
    "LazyCache",
    "FileCache",
    "MarkdownCache",
    "ConfigCache",
    "RepomixCache",
    # Execution - REMOVED (now in skills/terminal)
    # Settings
    "Settings",
    "get_setting",
    "get_config_path",
    "get_commit_types",
    "get_commit_scopes",
    "get_commit_protocol",
    "has_setting",
    "list_setting_sections",
    "set_conf_dir",
    "get_conf_dir",
    # Utils
    "setup_logging",
    "get_logger",
    "is_safe_path",
    "is_safe_command",
    "read_file_safely",
    "write_file_safely",
    "load_env_from_file",
    "get_env",
    "log_decision",
    "run_subprocess",
    # Context
    "ProjectContext",
    "ContextRegistry",
    "get_project_context",
    "get_all_project_contexts",
    "list_project_languages",
    "has_project_context",
    "register_project_context",
    "initialize_project_contexts",
    "PythonContext",
    "NixContext",
    # Inference
    "InferenceClient",
    "PERSONAS",
    "build_persona_prompt",
    "_load_api_key_from_config",
    "DEFAULT_MODEL",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "DEFAULT_MAX_TOKENS",
    # Memory
    "ProjectMemory",
    # Instructions
    "get_instructions",
    "get_instruction",
    "get_all_instructions_merged",
    "list_instruction_names",
    "reload_instructions",
    # API Key
    "get_anthropic_api_key",
    "get_api_key",
    "ensure_api_key",
]
