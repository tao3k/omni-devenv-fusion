# mcp-core - Shared library for omni-devenv-fusion MCP servers
"""
Shared library providing common functionality for orchestrator.py and coder.py.

Modules:
- execution: Safe command execution (claudebox wrapper)
- memory: Project memory persistence (backlog-md wrapper)
- inference: LLM inference client (mistral-vibe wrapper)
- utils: Common utilities (logging, path checking)
- lazy_cache: Lazy-loading singleton caches for protocols and configs
- project_context: Project-specific coding context framework
- instructions: Eager-loaded project instructions (agent/instructions/)

Usage:
    from mcp_core.execution import SafeExecutor
    from mcp_core.memory import ProjectMemory
    from mcp_core.inference import InferenceClient
    from mcp_core.utils import setup_logging, is_safe_path
    from mcp_core.lazy_cache import LazyCache, FileCache, ConfigCache
    from mcp_core.project_context import get_project_context, ProjectContext, ContextRegistry
    from mcp_core.instructions import get_instructions, get_all_instructions_merged

    # Get all project instructions (eager loaded at session start)
    instructions = get_all_instructions_merged()
"""

__version__ = "1.2.0"

from .execution import SafeExecutor
from .memory import ProjectMemory
from .inference import InferenceClient, PERSONAS, build_persona_prompt
from .utils import setup_logging, is_safe_path, log_decision
from .lazy_cache import LazyCache, FileCache, MarkdownCache, ConfigCache, CompositeCache
from .project_context import (
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
from .instructions import (
    get_instructions,
    get_instruction,
    get_all_instructions_merged,
    list_instruction_names,
    reload_instructions,
)

__all__ = [
    "SafeExecutor",
    "ProjectMemory",
    "InferenceClient",
    "PERSONAS",
    "build_persona_prompt",
    "setup_logging",
    "is_safe_path",
    "log_decision",
    "LazyCache",
    "FileCache",
    "MarkdownCache",
    "ConfigCache",
    "CompositeCache",
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
    # Instructions
    "get_instructions",
    "get_instruction",
    "get_all_instructions_merged",
    "list_instruction_names",
    "reload_instructions",
]
