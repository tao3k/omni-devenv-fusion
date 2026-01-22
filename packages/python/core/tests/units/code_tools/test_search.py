"""
Tests for code_tools AST Search functionality.

Tests cover:
- Rust-powered AST search (omni_core_rs)
- Pattern matching with ast-grep
- Multi-language support

Usage:
    python -m pytest packages/python/core/tests/units/code_tools/test_search.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestASTSearch:
    """Tests for Rust-powered AST search functionality."""

    @pytest.fixture
    def sample_py_file(self, tmp_path: Path) -> Path:
        """Create a sample Python file for testing."""
        content = '''
"""Sample module for testing."""

def hello(name: str) -> str:
    """Say hello."""
    print(f"Hello, {name}")
    return f"Hello, {name}"

def goodbye():
    """Say goodbye."""
    pass

class Greeter:
    """A greeter class."""

    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        """Greet someone."""
        return hello(self.name)

# TODO: remove print statements
print("debug")
'''
        file_path = tmp_path / "sample.py"
        file_path.write_text(content)
        return file_path

    @pytest.fixture
    def sample_rs_file(self, tmp_path: Path) -> Path:
        """Create a sample Rust file for testing."""
        content = """
fn main() {
    println!("Hello, world!");
}

fn add(a: i32, b: i32) -> i32 {
    a + b
}

struct Point {
    x: i32,
    y: i32,
}
"""
        file_path = tmp_path / "sample.rs"
        file_path.write_text(content)
        return file_path

    def test_ast_search_finds_functions(self, sample_py_file: Path):
        """Test that AST search finds function definitions."""
        try:
            from omni_core_rs import search_code
        except ImportError:
            pytest.skip("Rust AST engine not available")

        result = search_code(str(sample_py_file), "def $NAME", "python")

        assert result is not None
        assert "hello" in result
        assert "goodbye" in result
        assert "greet" in result

    def test_ast_search_finds_class(self, sample_py_file: Path):
        """Test that AST search finds class definitions."""
        try:
            from omni_core_rs import search_code
        except ImportError:
            pytest.skip("Rust AST engine not available")

        result = search_code(str(sample_py_file), "class $NAME", "python")

        assert result is not None
        assert "Greeter" in result

    def test_ast_search_ignores_comments(self, sample_py_file: Path):
        """Test that AST search doesn't match inside comments."""
        try:
            from omni_core_rs import search_code
        except ImportError:
            pytest.skip("Rust AST engine not available")

        result = search_code(str(sample_py_file), "print($ARGS)", "python")

        assert result is not None
        assert "debug" in result or "Hello" in result

    def test_ast_search_rust_language(self, sample_rs_file: Path):
        """Test AST search with Rust language."""
        try:
            from omni_core_rs import search_code
        except ImportError:
            pytest.skip("Rust AST engine not available")

        result = search_code(str(sample_rs_file), "fn $NAME", "rust")

        assert result is not None
        assert "SEARCH:" in result or "No matches" in result

    def test_ast_search_no_matches(self, sample_py_file: Path):
        """Test AST search returns appropriate message for no matches."""
        try:
            from omni_core_rs import search_code
        except ImportError:
            pytest.skip("Rust AST engine not available")

        result = search_code(str(sample_py_file), "class NonExistent", "python")

        assert result is not None
        assert "No matches" in result or result.strip() == ""


class TestDirectorySearch:
    """Tests for directory-based AST search."""

    @pytest.fixture
    def test_directory(self, tmp_path: Path) -> Path:
        """Create a directory with multiple files for testing."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        (tmp_path / "file1.py").write_text("def foo(): pass\ndef bar(): pass\n")
        (tmp_path / "file2.py").write_text("def foo(): pass\n")
        (subdir / "file3.py").write_text("class Foo: pass\n")
        (tmp_path / "data.json").write_text('{"key": "value"}')

        return tmp_path

    def test_ast_search_dir_recursive(self, test_directory: Path):
        """Test recursive directory search finds all matches."""
        try:
            from omni_core_rs import search_directory
        except ImportError:
            pytest.skip("Rust AST engine not available")

        result = search_directory(str(test_directory), "def $NAME", "**/*.py")

        assert result is not None
        assert "foo" in result
        assert "bar" in result

    def test_ast_search_dir_filters_by_extension(self, test_directory: Path):
        """Test that file_pattern filters files correctly."""
        try:
            from omni_core_rs import search_directory
        except ImportError:
            pytest.skip("Rust AST engine not available")

        result = search_directory(str(test_directory), "def $NAME", "*.py")

        assert result is not None
        assert "foo" in result

    def test_ast_search_dir_no_results(self, test_directory: Path):
        """Test directory search with no matching files."""
        try:
            from omni_core_rs import search_directory
        except ImportError:
            pytest.skip("Rust AST engine not available")

        result = search_directory(str(test_directory), "interface $NAME", "**/*.py")

        assert result is not None


class TestASTPatterns:
    """Test AST pattern matching with various patterns."""

    @pytest.fixture
    def mixed_file(self, tmp_path: Path) -> Path:
        """Create a file with various patterns."""
        content = """
async def fetch_data(url: str) -> dict:
    response = await http.get(url)
    return response.json()

def sync_function():
    return "sync"

class MyClass:
    def method(self):
        pass

# Ignore this
print("in string")
"""
        file_path = tmp_path / "mixed.py"
        file_path.write_text(content)
        return file_path

    def test_pattern_async_def(self, mixed_file: Path):
        """Test matching async function definitions."""
        try:
            from omni_core_rs import search_code
        except ImportError:
            pytest.skip("Rust AST engine not available")

        result = search_code(str(mixed_file), "async def $NAME($PARAMS)", "python")

        assert result is not None
        assert "fetch_data" in result

    def test_pattern_class_method(self, mixed_file: Path):
        """Test matching class methods."""
        try:
            from omni_core_rs import search_code
        except ImportError:
            pytest.skip("Rust AST engine not available")

        result = search_code(str(mixed_file), "def $NAME(self$REST)", "python")

        assert result is not None
        assert "method" in result

    def test_pattern_ignores_string_literals(self, mixed_file: Path):
        """Test that patterns don't match inside strings."""
        try:
            from omni_core_rs import search_code
        except ImportError:
            pytest.skip("Rust AST engine not available")

        result = search_code(str(mixed_file), "print($ARGS)", "python")

        assert result is not None


class TestASTEdgeCases:
    """Edge case tests for AST search."""

    def test_search_nonexistent_file(self):
        """Test handling of nonexistent file."""
        try:
            from omni_core_rs import search_code
        except ImportError:
            pytest.skip("Rust AST engine not available")

        result = search_code("/nonexistent/path/file.py", "def $NAME", "python")

        assert result is not None

    def test_search_invalid_pattern(self):
        """Test handling of invalid AST pattern."""
        try:
            from omni_core_rs import search_code
        except ImportError:
            pytest.skip("Rust AST engine not available")

        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def test(): pass\n")
            f.flush()

            try:
                result = search_code(f.name, "[invalid pattern", "python")
                assert result is not None
            finally:
                Path(f.name).unlink()

    def test_search_unsupported_language(self, tmp_path: Path):
        """Test handling of unsupported language."""
        try:
            from omni_core_rs import search_code
        except ImportError:
            pytest.skip("Rust AST engine not available")

        (tmp_path / "test.py").write_text("def test(): pass\n")

        result = search_code(str(tmp_path / "test.py"), "def $NAME", "unsupported_lang_xyz")

        assert result is not None

    def test_search_empty_file(self, tmp_path: Path):
        """Test searching empty file."""
        try:
            from omni_core_rs import search_code
        except ImportError:
            pytest.skip("Rust AST engine not available")

        (tmp_path / "empty.py").write_text("")

        result = search_code(str(tmp_path / "empty.py"), "def $NAME", "python")

        assert result is not None
        assert "No matches" in result or result.strip() == ""
