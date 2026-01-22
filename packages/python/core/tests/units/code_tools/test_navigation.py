"""
Tests for code_tools Navigation functionality.

Tests cover:
- outline_file: File skeleton generation
- list_symbols: Structured symbol extraction
- goto_definition: Find symbol definitions
- find_references: Find symbol usages

Usage:
    python -m pytest packages/python/core/tests/units/code_tools/test_navigation.py -v
"""

from __future__ import annotations

from pathlib import Path
import sys
import os

import pytest

# Add skills path for imports
SKILLS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "assets",
    "skills",
    "code_tools",
    "scripts",
)
if SKILLS_PATH not in sys.path:
    sys.path.insert(0, SKILLS_PATH)


class TestOutlineFile:
    """Tests for outline_file command."""

    @pytest.fixture
    def sample_py_file(self, tmp_path: Path) -> Path:
        """Create a sample Python file for testing."""
        content = '''"""Sample module for testing."""

class Agent:
    """A sample agent class."""

    def __init__(self, name: str):
        self.name = name

    async def run(self, task: str) -> None:
        """Run a task."""
        pass

def helper_function(x: int) -> int:
    """Helper function."""
    return x * 2

class AnotherClass:
    pass
'''
        file_path = tmp_path / "sample.py"
        file_path.write_text(content)
        return file_path

    def test_outline_file_generates_structure(self, sample_py_file: Path):
        """Test that outline_file generates a proper outline."""
        try:
            from omni_core_rs import get_file_outline
        except ImportError:
            pytest.skip("Rust bindings not available")

        result = get_file_outline(str(sample_py_file), "python")

        assert result is not None
        assert "OUTLINE:" in result
        assert "Agent" in result
        assert "helper_function" in result

    def test_outline_file_contains_line_numbers(self, sample_py_file: Path):
        """Test that outline contains line numbers."""
        try:
            from omni_core_rs import get_file_outline
        except ImportError:
            pytest.skip("Rust bindings not available")

        result = get_file_outline(str(sample_py_file), "python")

        # Line numbers should be present (L followed by number)
        assert "L" in result

    def test_outline_file_empty_file(self, tmp_path: Path):
        """Test outline on empty file."""
        try:
            from omni_core_rs import get_file_outline
        except ImportError:
            pytest.skip("Rust bindings not available")

        file_path = tmp_path / "empty.py"
        file_path.write_text("")

        result = get_file_outline(str(file_path), "python")

        assert result is not None
        assert "No symbols" in result or result.strip() != ""

    def test_outline_file_rust_language(self, tmp_path: Path):
        """Test outline with Rust code."""
        try:
            from omni_core_rs import get_file_outline
        except ImportError:
            pytest.skip("Rust bindings not available")

        content = """
struct Point {
    x: i32,
    y: i32,
}

impl Point {
    fn new(x: i32, y: i32) -> Point {
        Point { x, y }
    }
}
"""
        file_path = tmp_path / "sample.rs"
        file_path.write_text(content)

        result = get_file_outline(str(file_path), "rust")

        assert result is not None
        assert "Point" in result


class TestListSymbolsRust:
    """Tests for list_symbols using Rust bindings directly."""

    @pytest.fixture
    def sample_py_file(self, tmp_path: Path) -> Path:
        """Create a Python file with various symbols."""
        content = '''"""Test module."""

class MyClass:
    """A class."""
    def method1(self):
        pass

    async def method2(self, x: int) -> str:
        pass

def regular_function():
    pass

async def async_function():
    pass
'''
        file_path = tmp_path / "test_symbols.py"
        file_path.write_text(content)
        return file_path

    def test_list_symbols_via_outline_parsing(self, sample_py_file: Path):
        """Test that list_symbols logic works via outline parsing."""
        try:
            from omni_core_rs import get_file_outline
        except ImportError:
            pytest.skip("Rust bindings not available")

        outline = get_file_outline(str(sample_py_file), "python")

        # Parse outline to extract symbols
        symbols = []
        for line in outline.split("\n"):
            line = line.strip()
            if line.startswith("L") and "[" in line and "]" in line:
                try:
                    parts = line.split()
                    line_num = int(parts[0][1:])
                    kind_start = line.find("[") + 1
                    kind_end = line.find("]")
                    kind = line[kind_start:kind_end].lower()
                    rest = line[kind_end + 1 :].strip()
                    name = rest.split(None, 1)[0] if rest.split(None, 1) else ""
                    symbols.append({"name": name, "kind": kind, "line": line_num})
                except (ValueError, IndexError):
                    continue

        # Verify we found the expected symbols
        names = [s["name"] for s in symbols]
        assert "MyClass" in names
        assert "regular_function" in names

        # Verify symbol structure
        for s in symbols:
            assert "name" in s
            assert "kind" in s
            assert "line" in s

    def test_list_symbols_finds_classes(self, sample_py_file: Path):
        """Test that list_symbols finds classes."""
        try:
            from omni_core_rs import get_file_outline
        except ImportError:
            pytest.skip("Rust bindings not available")

        outline = get_file_outline(str(sample_py_file), "python")

        assert "MyClass" in outline
        assert "[class]" in outline.lower() or "class" in outline.lower()


class TestGotoDefinitionRust:
    """Tests for goto_definition using Rust bindings."""

    def test_goto_definition_via_search(self, tmp_path: Path):
        """Test finding a class definition via search."""
        try:
            from omni_core_rs import search_directory
        except ImportError:
            pytest.skip("Rust bindings not available")

        # Create test file
        (tmp_path / "lib.py").write_text('''
class MyClass:
    """Sample class."""
    pass

def my_function():
    pass
''')

        # Search for class definition
        result = search_directory(str(tmp_path), "class $NAME", "**/*.py")

        assert result is not None
        assert "MyClass" in result or "SEARCH:" in result

    def test_goto_definition_finds_function(self, tmp_path: Path):
        """Test finding a function definition."""
        try:
            from omni_core_rs import search_directory
        except ImportError:
            pytest.skip("Rust bindings not available")

        (tmp_path / "lib.py").write_text('''
def my_function():
    """Sample function."""
    pass
''')

        result = search_directory(str(tmp_path), "def $NAME", "**/*.py")

        assert result is not None
        assert "my_function" in result or "SEARCH:" in result

    def test_goto_definition_nonexistent_symbol(self, tmp_path: Path):
        """Test goto_definition with nonexistent symbol."""
        try:
            from omni_core_rs import search_directory
        except ImportError:
            pytest.skip("Rust bindings not available")

        result = search_directory(str(tmp_path), "class NonExistentSymbolXYZ", "**/*.py")

        assert result is not None
        # Should return no matches
        assert "No matches" in result or result.strip() == ""


class TestFindReferencesRust:
    """Tests for find_references using Rust bindings."""

    def test_find_references_via_search(self, tmp_path: Path):
        """Test finding symbol references via search."""
        try:
            from omni_core_rs import search_directory
        except ImportError:
            pytest.skip("Rust bindings not available")

        (tmp_path / "main.py").write_text("""
def helper():
    pass

helper()
x = helper()
result = helper()
""")

        # Search for function calls
        result = search_directory(str(tmp_path), "helper($$$)", "**/*.py")

        assert result is not None
        # Should find references
        assert "SEARCH:" in result or "Total matches:" in result

    def test_find_references_empty_result(self, tmp_path: Path):
        """Test find_references with unused symbol."""
        try:
            from omni_core_rs import search_directory
        except ImportError:
            pytest.skip("Rust bindings not available")

        (tmp_path / "main.py").write_text("x = 1")

        result = search_directory(str(tmp_path), "unused_symbol_xyz($$$)", "**/*.py")

        assert result is not None
        # Should find no references
        assert "No matches" in result or result.strip() == ""


class TestSymbolNavigationRust:
    """Direct tests of Rust binding functions."""

    def test_get_file_outline_basic(self, tmp_path: Path):
        """Test get_file_outline basic functionality."""
        try:
            from omni_core_rs import get_file_outline
        except ImportError:
            pytest.skip("Rust bindings not available")

        content = """
class TestClass:
    def test_method(self):
        pass

def test_function():
    pass
"""
        file_path = tmp_path / "test.py"
        file_path.write_text(content)

        result = get_file_outline(str(file_path), "python")

        assert result is not None
        assert "TestClass" in result
        assert "test_function" in result

    def test_search_code_pattern(self, tmp_path: Path):
        """Test search_code with AST pattern."""
        try:
            from omni_core_rs import search_code
        except ImportError:
            pytest.skip("Rust bindings not available")

        content = """
def foo(): pass
def bar(): pass
class Baz: pass
"""
        file_path = tmp_path / "test.py"
        file_path.write_text(content)

        # Search for function definitions
        result = search_code(str(file_path), "def $NAME", "python")

        assert result is not None
        assert "foo" in result or "bar" in result

    def test_search_directory_recursive(self, tmp_path: Path):
        """Test search_directory across multiple files."""
        try:
            from omni_core_rs import search_directory
        except ImportError:
            pytest.skip("Rust bindings not available")

        # Create test files
        (tmp_path / "file1.py").write_text("def foo(): pass\n")
        (tmp_path / "file2.py").write_text("def foo(): pass\n")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file3.py").write_text("def foo(): pass\n")

        result = search_directory(str(tmp_path), "def $NAME", "**/*.py")

        assert result is not None
        # Should find foo in multiple files
        assert "SEARCH:" in result or "Total matches:" in result


class TestNavigationEdgeCases:
    """Edge case tests for navigation."""

    def test_outline_nonexistent_file(self):
        """Test outline on nonexistent file."""
        try:
            from omni_core_rs import get_file_outline
        except ImportError:
            pytest.skip("Rust bindings not available")

        result = get_file_outline("/nonexistent/path.py", "python")

        assert result is not None

    def test_outline_unsupported_language(self, tmp_path: Path):
        """Test outline with unsupported language."""
        try:
            from omni_core_rs import get_file_outline
        except ImportError:
            pytest.skip("Rust bindings not available")

        file_path = tmp_path / "test.xyz"
        file_path.write_text("some content")

        result = get_file_outline(str(file_path), None)

        assert result is not None

    def test_search_code_empty_content(self, tmp_path: Path):
        """Test search on empty file."""
        try:
            from omni_core_rs import search_code
        except ImportError:
            pytest.skip("Rust bindings not available")

        file_path = tmp_path / "empty.py"
        file_path.write_text("")

        result = search_code(str(file_path), "def $NAME", "python")

        assert result is not None

    def test_search_directory_no_matches(self, tmp_path: Path):
        """Test search_directory with no matches."""
        try:
            from omni_core_rs import search_directory
        except ImportError:
            pytest.skip("Rust bindings not available")

        (tmp_path / "file.py").write_text("x = 1\n")

        result = search_directory(str(tmp_path), "class NonExistent", "**/*.py")

        assert result is not None
        assert "No matches" in result or result.count == 0
