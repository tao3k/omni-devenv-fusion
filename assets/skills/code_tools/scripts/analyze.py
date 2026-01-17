"""
code_tools/scripts/analyze.py - Code Analysis Commands

Phase 68: Migrated from code_insight.
Static code analysis using pure Python AST.
"""

import ast
from pathlib import Path
from typing import List

import structlog

from agent.skills.decorators import skill_command
from common.config_paths import get_project_root

logger = structlog.get_logger(__name__)


# =============================================================================
# Pure Helper Functions (The "Hands")
# =============================================================================


def _is_tool_decorator(decorator: ast.AST) -> bool:
    """Check if a decorator is @tool or @mcp.tool."""
    # Case: @tool
    if isinstance(decorator, ast.Name) and decorator.id == "tool":
        return True
    # Case: @mcp.tool
    if isinstance(decorator, ast.Attribute) and decorator.attr == "tool":
        return True
    # Case: @tool() or @mcp.tool()
    if isinstance(decorator, ast.Call):
        func = decorator.func
        if isinstance(func, ast.Name) and func.id == "tool":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "tool":
            return True
    return False


class _ToolVisitor(ast.NodeVisitor):
    """Find all @tool decorated functions."""

    def __init__(self):
        self.tools: List[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if any(_is_tool_decorator(d) for d in node.decorator_list):
            self.tools.append(node.name)
        self.generic_visit(node)


# =============================================================================
# Atomic Tools (Dumb, Stateless)
# =============================================================================


@skill_command(
    name="find_tools",
    category="read",
    description="""
    Finds all @tool decorated functions in a Python file.

    Parses the Python AST to locate functions with `@tool` or `@mcp.tool` decorators.

    Args:
        file_path: Relative path to the Python file from project root.

    Returns:
        List of tool function names, one per line with `-` prefix.
        Returns error if file not found, syntax error, or path outside project.

    Example:
        @omni("code_tools.find_tools", {"file_path": "agent/skills/git/tools.py"})
    """,
)
async def find_tools(file_path: str) -> str:
    root = get_project_root()
    target = (root / file_path).resolve()

    if not str(target).startswith(str(root)):
        return "Error: Access denied to paths outside project root."

    if not target.exists():
        return f"Error: File not found: {file_path}"

    try:
        content = target.read_text(encoding="utf-8")
        tree = ast.parse(content)
        visitor = _ToolVisitor()
        visitor.visit(tree)

        if not visitor.tools:
            return f"No tools found in `{file_path}`"

        return "\n".join(f"- {t}" for t in visitor.tools)
    except SyntaxError as e:
        return f"Syntax Error: {e}"
    except Exception as e:
        return f"Error: {e}"


@skill_command(
    name="count_lines",
    category="read",
    description="""
    Counts lines of code in a file.

    Args:
        file_path: Relative path to the file from project root.

    Returns:
        String with format `{file_path}: {count} lines`.
        Returns error if file not found.

    Example:
        @omni("code_tools.count_lines", {"file_path": "agent/core/engine.py"})
    """,
)
async def count_lines(file_path: str) -> str:
    root = get_project_root()
    target = (root / file_path).resolve()

    if not target.exists():
        return f"Error: File not found: {file_path}"

    lines = target.read_text().splitlines()
    return f"{file_path}: {len(lines)} lines"
