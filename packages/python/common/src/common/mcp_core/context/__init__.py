"""
context - Project-specific context framework.

Phase 29: Protocol-based design with slots=True.

Modules:
- base.py: ProjectContext base class
- registry.py: ContextRegistry and built-in contexts

Usage:
    from mcp_core.context import ProjectContext, ContextRegistry

    class GoContext(ProjectContext):
        LANG_ID = "go"
        CATEGORIES = ["tooling", "patterns", "conventions"]

        def _load_tooling(self) -> str:
            return "## 🛠️ Go Tooling..."

    ContextRegistry.register(GoContext())
    context = ContextRegistry.get("go")
"""

from .base import ProjectContext
from .registry import ContextRegistry, PythonContext, NixContext


def get_project_context(lang: str, category: str | None = None) -> str:
    """Get project-specific context for a language.

    This is the main API for retrieving project context.

    Args:
        lang: Language ID (python, nix, etc.)
        category: Optional category (tooling, patterns, architecture, conventions)
                 If None, returns all categories merged.

    Returns:
        Project context string, or empty string if not found.

    Examples:
        # Get all Python context
        context = get_project_context("python")

        # Get specific category
        tooling = get_project_context("python", category="tooling")
    """
    context = ContextRegistry.get(lang)
    if context is None:
        return ""
    return context.get(category)


def get_all_project_contexts() -> dict[str, dict[str, str]]:
    """Get all registered project contexts.

    Returns:
        Dictionary of lang_id -> {category -> content}.
    """
    result: dict[str, dict[str, str]] = {}
    for lang_id in ContextRegistry.list_languages():
        context = ContextRegistry.get(lang_id)
        if context:
            result[lang_id] = {cat: context.get(cat) for cat in context.categories}
    return result


def list_project_languages() -> list[str]:
    """List all registered language IDs.

    Returns:
        List of language IDs.
    """
    return ContextRegistry.list_languages()


def has_project_context(lang: str) -> bool:
    """Check if context exists for a language.

    Args:
        lang: Language ID.

    Returns:
        True if context exists.
    """
    return ContextRegistry.has(lang)


def register_project_context(context: ProjectContext) -> None:
    """Register a custom project context.

    Use this to add support for new languages:

    class GoContext(ProjectContext):
        LANG_ID = "go"
        CATEGORIES = ["tooling", "patterns", "conventions"]

        def _load_tooling(self) -> str:
            return "## 🛠️ Go Tooling..."

        def _load_patterns(self) -> str:
            return "## 🔄 Go Patterns..."

    register_project_context(GoContext())
    """
    ContextRegistry.register(context)


def initialize_project_contexts() -> None:
    """Initialize all project contexts (for MCP server startup).

    Call this at MCP server startup to pre-load all contexts.
    """
    ContextRegistry.initialize_all()


__all__ = [
    # Base
    "ProjectContext",
    # Registry
    "ContextRegistry",
    # Built-in contexts
    "PythonContext",
    "NixContext",
    # API
    "get_project_context",
    "get_all_project_contexts",
    "list_project_languages",
    "has_project_context",
    "register_project_context",
    "initialize_project_contexts",
]
