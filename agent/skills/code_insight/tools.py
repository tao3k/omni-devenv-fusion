"""
Code Insight Tools - Atomic, Dumb, Single-Purpose

Tools are like Unix commands: they do ONE thing well.
No business logic in tools - only pure execution.
"""
import ast
from pathlib import Path
from typing import List
from mcp.server.fastmcp import FastMCP

from common.mcp_core.config_paths import get_project_root


# =============================================================================
# Pure Helper Functions (The "Hands")
# =============================================================================

def _is_tool_decorator(decorator: ast.AST) -> bool:
    """Check if a decorator is @tool or @mcp.tool."""
    # Case: @tool
    if isinstance(decorator, ast.Name) and decorator.id == 'tool':
        return True
    # Case: @mcp.tool
    if isinstance(decorator, ast.Attribute) and decorator.attr == 'tool':
        return True
    # Case: @tool() or @mcp.tool()
    if isinstance(decorator, ast.Call):
        func = decorator.func
        if isinstance(func, ast.Name) and func.id == 'tool':
            return True
        if isinstance(func, ast.Attribute) and func.attr == 'tool':
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

async def find_tools(file_path: str) -> str:
    """
    Find all @tool decorated functions in a Python file.

    Args:
        file_path: Relative path to Python file.

    Returns:
        List of tool names, one per line.
    """
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


async def count_lines(file_path: str) -> str:
    """
    Count lines of code in a file.

    Args:
        file_path: Relative path to file.

    Returns:
        Line count summary.
    """
    root = get_project_root()
    target = (root / file_path).resolve()

    if not target.exists():
        return f"Error: File not found: {file_path}"

    lines = target.read_text().splitlines()
    return f"{file_path}: {len(lines)} lines"


# =============================================================================
# Registration
# =============================================================================

def register(mcp: FastMCP):
    """Register atomic code insight tools."""
    mcp.tool()(find_tools)
    mcp.tool()(count_lines)
