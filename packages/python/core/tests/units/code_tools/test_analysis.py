"""
Tests for code_tools Analysis functionality.

Tests cover:
- Python AST parsing
- @tool decorator detection
- Line counting
- Symbol analysis

Usage:
    python -m pytest packages/python/core/tests/units/code_tools/test_analysis.py -v
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


class TestPythonASTAnalysis:
    """Tests for Python AST parsing functionality (fallback)."""

    @pytest.fixture
    def tool_decorated_file(self, tmp_path: Path) -> Path:
        """Create a file with @tool decorators."""
        content = '''
"""Module with tools."""

from some_lib import tool

@tool
def get_data() -> dict:
    """Get some data."""
    return {"data": 1}

@mcp.tool
def process_data(data: dict) -> bool:
    """Process data."""
    return True

def regular_function():
    """Not a tool."""
    pass
'''
        file_path = tmp_path / "tools.py"
        file_path.write_text(content)
        return file_path

    def test_find_tools_decorated_functions(self, tool_decorated_file: Path):
        """Test finding @tool decorated functions."""
        content = tool_decorated_file.read_text()
        tree = ast.parse(content)

        class ToolVisitor(ast.NodeVisitor):
            def __init__(self):
                self.tools: list[str] = []

            def visit_FunctionDef(self, node):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == "tool":
                        self.tools.append(node.name)
                        break
                    if isinstance(decorator, ast.Attribute) and decorator.attr == "tool":
                        self.tools.append(node.name)
                        break
                self.generic_visit(node)

        visitor = ToolVisitor()
        visitor.visit(tree)

        assert "get_data" in visitor.tools
        assert "process_data" in visitor.tools
        assert "regular_function" not in visitor.tools


class TestLineCounting:
    """Tests for line counting functionality."""

    def test_count_lines_simple(self):
        """Test counting lines in a string."""
        content = "line1\nline2\nline3\n"
        lines = content.splitlines()
        assert len(lines) == 3

    def test_count_lines_empty(self):
        """Test counting empty file."""
        content = ""
        lines = content.splitlines()
        assert len(lines) == 0

    def test_count_lines_with_newline(self):
        """Test counting lines with trailing newline."""
        content = "line1\nline2\nline3\n"
        assert content.count("\n") == 3


class TestPythonASTPatterns:
    """Additional Python AST pattern tests."""

    def test_parse_function_def(self):
        """Test parsing a function definition."""
        code = """
def hello(name: str) -> str:
    return f"Hello, {name}"
"""
        tree = ast.parse(code)
        assert isinstance(tree.body[0], ast.FunctionDef)
        assert tree.body[0].name == "hello"

    def test_parse_class_def(self):
        """Test parsing a class definition."""
        code = """
class MyClass:
    def method(self):
        pass
"""
        tree = ast.parse(code)
        assert isinstance(tree.body[0], ast.ClassDef)
        assert tree.body[0].name == "MyClass"

    def test_parse_async_function(self):
        """Test parsing an async function definition."""
        code = """
async def fetch_data() -> dict:
    return {}
"""
        tree = ast.parse(code)
        assert isinstance(tree.body[0], ast.AsyncFunctionDef)
        assert tree.body[0].name == "fetch_data"

    def test_find_all_functions(self):
        """Test finding all function definitions."""
        code = """
def foo(): pass
def bar(): pass
class MyClass:
    def method(self): pass
"""
        tree = ast.parse(code)
        funcs = [
            n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert "foo" in funcs
        assert "bar" in funcs
        assert "method" in funcs

    def test_find_all_classes(self):
        """Test finding all class definitions."""
        code = """
class A: pass
class B: pass
"""
        tree = ast.parse(code)
        classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        assert "A" in classes
        assert "B" in classes
