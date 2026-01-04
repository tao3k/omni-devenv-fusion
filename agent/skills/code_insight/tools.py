import ast
from pathlib import Path
from mcp.server.fastmcp import FastMCP, Context

# Direct reference to Common package for path utilities
from common.mcp_core.config_paths import get_project_root


# =============================================================================
# Module-Level Tool Definitions (Accessible via 'skill' proxy & 'getattr')
# =============================================================================

async def analyze_code_structure(file_path: str, ctx: Context = None) -> str:
    """
    Static analysis of a Python file to extract functions, classes, and tools.
    Use this to understand code capability without importing/running it.

    Args:
        file_path: Relative path to the file (e.g., "packages/python/agent/main.py")
    """
    root = get_project_root()
    target = (root / file_path).resolve()

    # Security check: prevent reading files outside project
    if not str(target).startswith(str(root)):
        return "Security Alert: Access denied to paths outside project root."

    if not target.exists():
        return f"File not found: {file_path}"

    try:
        content = target.read_text(encoding="utf-8")
        tree = ast.parse(content)

        summary = {
            "classes": [],
            "functions": [],
            "mcp_tools": []
        }

        for node in ast.walk(tree):
            # 1. Identify classes
            if isinstance(node, ast.ClassDef):
                summary["classes"].append(node.name)

            # 2. Identify functions
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = f"{node.name}"
                if isinstance(node, ast.AsyncFunctionDef):
                    func_info += " (async)"
                summary["functions"].append(func_info)

                # 3. Detect @tool decorators
                for decorator in node.decorator_list:
                    is_tool = False
                    # Case A: @tool
                    if isinstance(decorator, ast.Name) and decorator.id == 'tool':
                        is_tool = True
                    # Case B: @mcp.tool
                    elif isinstance(decorator, ast.Attribute) and decorator.attr == 'tool':
                        is_tool = True
                    # Case C: @mcp.tool() or @tool()
                    elif isinstance(decorator, ast.Call):
                        func = decorator.func
                        if isinstance(func, ast.Name) and func.id == 'tool':
                            is_tool = True
                        elif isinstance(func, ast.Attribute) and func.attr == 'tool':
                            is_tool = True

                    if is_tool:
                        summary["mcp_tools"].append(node.name)

        # Format output
        output = [f"Code Structure Analysis: `{file_path}`"]

        if summary["mcp_tools"]:
            output.append("\nMCP Tools Detected:")
            for t in summary["mcp_tools"]:
                output.append(f"- {t}")

        if summary["classes"]:
            output.append(f"\nClasses ({len(summary['classes'])}): " + ", ".join(summary["classes"]))

        output.append(f"\nFunctions ({len(summary['functions'])}): {len(summary['functions'])} total")

        return "\n".join(output)

    except Exception as e:
        return f"Parse Error: {str(e)}"


# =============================================================================
# Registration
# =============================================================================

def register(mcp: FastMCP):
    """Register All Code Insight Tools from Module Scope."""
    mcp.tool()(analyze_code_structure)
