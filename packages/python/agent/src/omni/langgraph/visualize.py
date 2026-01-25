"""
omni/langgraph/visualize.py - LangGraph Workflow Visualization

Usage:
    from omni.langgraph.visualize import visualize_workflow, register_workflow

    # Register a workflow
    register_workflow("smart_commit", diagram)

    # Get diagram
    diagram = visualize_workflow("smart_commit")
"""

from enum import Enum


class VisualFormat(str, Enum):
    """Output format."""

    MERMAID = "mermaid"


class _WorkflowRegistry:
    """Simple registry for workflow diagrams."""

    def __init__(self):
        self._diagrams: dict[str, str] = {}

    def register(self, name: str, diagram: str) -> None:
        self._diagrams[name] = diagram

    def get(self, name: str) -> str | None:
        return self._diagrams.get(name)

    def list(self) -> list[str]:
        return list(self._diagrams.keys())

    def clear(self, prefix: str | None = None) -> int:
        """Clear workflows matching prefix. Returns count cleared."""
        if prefix is None:
            count = len(self._diagrams)
            self._diagrams.clear()
            return count
        keys = [k for k in self._diagrams if k.startswith(prefix)]
        for k in keys:
            del self._diagrams[k]
        return len(keys)


# Global registry
_registry = _WorkflowRegistry()


def register_workflow(name: str, diagram: str) -> None:
    """Register a workflow diagram (overwrites existing)."""
    _registry.register(name, diagram)


def visualize_workflow(name: str) -> str:
    """Get workflow diagram by name."""
    diagram = _registry.get(name)
    if diagram:
        return diagram
    available = _registry.list()
    if available:
        return f"Workflow '{name}' not found.\n\nAvailable: {', '.join(available)}"
    return f"Workflow '{name}' not found. No workflows registered."


def list_workflows() -> str:
    """List all registered workflows."""
    workflows = _registry.list()
    if not workflows:
        return "No workflows registered."
    return "Registered workflows:\n" + "\n".join(f"- {w}" for w in workflows)


def clear_workflows(prefix: str) -> int:
    """Clear all workflows matching prefix (for hot reload)."""
    return _registry.clear(prefix)
