# mcp-core - Shared library for omni-devenv-fusion MCP servers
"""
Shared library providing common functionality for orchestrator.py and coder.py.

Modules:
- execution: Safe command execution (claudebox wrapper)
- memory: Project memory persistence (backlog-md wrapper)
- inference: LLM inference client (mistral-vibe wrapper)
- utils: Common utilities (logging, path checking)

Usage:
    from mcp_core.execution import SafeExecutor
    from mcp_core.memory import ProjectMemory
    from mcp_core.inference import InferenceClient
    from mcp_core.utils import setup_logging, is_safe_path
"""

__version__ = "1.0.0"

from .execution import SafeExecutor
from .memory import ProjectMemory
from .inference import InferenceClient, PERSONAS, build_persona_prompt
from .utils import setup_logging, is_safe_path, log_decision

__all__ = [
    "SafeExecutor",
    "ProjectMemory",
    "InferenceClient",
    "PERSONAS",
    "build_persona_prompt",
    "setup_logging",
    "is_safe_path",
    "log_decision",
]
