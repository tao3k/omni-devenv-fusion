"""
MCP server prompt templates.

Domain-specific system prompts for different agent modes:
default, researcher, developer.

Supports dynamic prompt registration for 10,000+ skills.
"""

from __future__ import annotations

from typing import Any, Callable


PROMPTS: dict[str, dict[str, str]] = {
    "default": {
        "description": "Standard Omni Agent system prompt",
        "content": (
            "You are Omni-Dev Fusion, an advanced AI programming assistant.\n\n"
            "Core Principles:\n"
            "1. Use high-level skills (researcher, code_tools, git_smart) first\n"
            "2. Use skill.discover when you need to find new capabilities\n"
            "3. Stop immediately if you are stuck in a loop\n"
            "4. Output 'EXIT_LOOP_NOW' only when the user's intent is fully satisfied\n\n"
            "You have access to:\n"
            "- File system operations (read, write, list, delete)\n"
            "- Git operations (status, commit, log, branch)\n"
            "- Research capabilities (web search, code analysis)\n"
            "- Code execution and refactoring\n\n"
            "Always explain your reasoning before taking action."
        ),
    },
    "researcher": {
        "description": "Research-focused agent prompt",
        "content": (
            "You are Omni-Researcher, an AI assistant specialized in "
            "code analysis and research.\n\n"
            "Your approach:\n"
            "1. First understand the codebase structure using researcher skills\n"
            "2. Use structural code analysis to find relevant code\n"
            "3. Document your findings clearly\n"
            "4. Provide actionable insights\n\n"
            "Focus on:\n"
            "- Code architecture understanding\n"
            "- Dependency analysis\n"
            "- Pattern discovery\n"
            "- Documentation generation"
        ),
    },
    "developer": {
        "description": "Code-focused agent prompt",
        "content": (
            "You are Omni-Developer, an AI assistant specialized in "
            "code modification and debugging.\n\n"
            "Your approach:\n"
            "1. Understand the task and existing code structure\n"
            "2. Make minimal, focused changes\n"
            "3. Write tests for your changes\n"
            "4. Verify changes don't break existing functionality\n\n"
            "Focus on:\n"
            "- Implementing features correctly\n"
            "- Writing clean, maintainable code\n"
            "- Adding appropriate error handling\n"
            "- Testing thoroughly"
        ),
    },
}


# =============================================================================
# Dynamic Prompt Registration - For 10,000+ skills
# =============================================================================

# Registry for dynamically registered prompts
_DYNAMIC_PROMPTS: dict[str, Callable[[dict[str, str] | None], dict[str, str]]] = {}


def get_prompt(name: str) -> dict[str, str]:
    """Return a prompt template by name. Falls back to 'default'."""
    # Check dynamic prompts first
    if name in _DYNAMIC_PROMPTS:
        return _DYNAMIC_PROMPTS[name]({})
    return PROMPTS.get(name, PROMPTS["default"])


def get_prompt_with_args(name: str, arguments: dict[str, str] | None = None) -> dict[str, str]:
    """Get prompt with arguments, supporting dynamic prompts.

    Args:
        name: Prompt name.
        arguments: Optional arguments for template prompts.

    Returns:
        Prompt dict with description and content.
    """
    if name in _DYNAMIC_PROMPTS:
        return _DYNAMIC_PROMPTS[name](arguments or {})
    return PROMPTS.get(name, PROMPTS["default"])


def list_prompt_names() -> list[str]:
    """Return all available prompt template names."""
    return list(PROMPTS.keys()) + list(_DYNAMIC_PROMPTS.keys())


def list_all_prompts() -> list[str]:
    """Return all prompt names including dynamic ones."""
    return list_prompt_names()


def register_dynamic_prompt(
    name: str,
    description: str,
    content_fn: Callable[[dict[str, str] | None], str],
) -> None:
    """Register a dynamic prompt.

    Args:
        name: Prompt name (e.g., "skill.analyze")
        description: Prompt description.
        content_fn: Function that returns prompt content, accepts optional arguments.
    """
    _DYNAMIC_PROMPTS[name] = lambda args: {
        "description": description,
        "content": content_fn(args),
    }


def unregister_dynamic_prompt(name: str) -> bool:
    """Unregister a dynamic prompt.

    Args:
        name: Prompt name to remove.

    Returns:
        True if removed, False if not found.
    """
    if name in _DYNAMIC_PROMPTS:
        del _DYNAMIC_PROMPTS[name]
        return True
    return False


def clear_dynamic_prompts() -> None:
    """Clear all dynamic prompts."""
    _DYNAMIC_PROMPTS.clear()
