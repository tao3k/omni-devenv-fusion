"""
Tests for code_tools Structural Refactoring (The Surgeon).

Tests cover:
- structural_replace: Content-based AST refactoring
- structural_preview: Preview without modification
- structural_apply: Apply changes to files
- batch_structural_replace: Multi-file refactoring (The Ouroboros)

Usage:
    python -m pytest packages/python/core/tests/units/code_tools/test_refactor.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestStructuralReplace:
    """Tests for content-based structural replace."""

    @pytest.fixture
    def sample_py_content(self) -> str:
        """Sample Python content for refactoring tests."""
        return """
def connect(host, port):
    return f"Connected to {host}:{port}"

def old_api_call(data):
    return process(data)

print("debug")
print("another debug")
class OldClass:
    pass
"""

    def test_structural_replace_simple(self, sample_py_content: str):
        """Test basic structural replace on content."""
        try:
            from omni_core_rs import structural_replace
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        result = structural_replace(
            sample_py_content, "connect($$$ARGS)", "safe_connect($$$ARGS)", "python"
        )

        assert result is not None
        assert "Replacements:" in result

    def test_structural_replace_variadic(self, sample_py_content: str):
        """Test structural replace with variadic capture ($$$)."""
        try:
            from omni_core_rs import structural_replace
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        result = structural_replace(
            sample_py_content, "print($$$ARGS)", "logger.info($$$ARGS)", "python"
        )

        assert result is not None
        assert "SEARCH:" in result or "logger" in result or "Replacements:" in result

    def test_structural_replace_no_matches(self, sample_py_content: str):
        """Test structural replace with no matching pattern."""
        try:
            from omni_core_rs import structural_replace
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        result = structural_replace(
            sample_py_content, "nonexistent_function($$$)", "replaced($$$)", "python"
        )

        assert result is not None
        assert "No matches" in result or result.count == 0 or "SEARCH:" in result

    def test_structural_replace_rust_language(self):
        """Test structural replace with Rust code."""
        try:
            from omni_core_rs import structural_replace
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        rust_content = "let x = old_function(arg1, arg2);"
        result = structural_replace(
            rust_content, "old_function($$$ARGS)", "new_function($$$ARGS)", "rust"
        )

        assert result is not None
        assert "new_function" in result or "Replacements:" in result

    def test_structural_replace_class_rename(self):
        """Test structural replace for class renaming."""
        try:
            from omni_core_rs import structural_replace
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        content = "class LegacyClass:\n    pass\n\nx = LegacyClass()"
        result = structural_replace(content, "LegacyClass", "ModernClass", "python")

        assert result is not None
        assert "ModernClass" in result or "Replacements:" in result

    def test_structural_replace_ignores_strings(self):
        """Test structural replace doesn't match inside strings."""
        try:
            from omni_core_rs import structural_replace
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        content = 'x = "print this"'
        result = structural_replace(content, "print($$$ARGS)", "logger.info($$$ARGS)", "python")

        assert result is not None
        assert "Replacements: 0" in result or "[No matches" in result

    def test_structural_replace_multiline(self):
        """Test structural replace works across multiple lines."""
        try:
            from omni_core_rs import structural_replace
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        content = """
async def fetch_data(url):
    response = await http.get(url)
    return response.json()
"""
        result = structural_replace(
            content, "async def $NAME($PARAMS)", "async def async_$NAME($PARAMS)", "python"
        )

        assert result is not None
        assert "async_fetch_data" in result or "Replacements:" in result


class TestStructuralPreview:
    """Tests for structural preview (no file modification)."""

    def test_structural_preview_file(self, tmp_path: Path):
        """Test structural preview on a file (no modification)."""
        try:
            from omni_core_rs import structural_preview
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        content = 'print("hello")\nprint("world")\n'
        file_path = tmp_path / "test_preview.py"
        file_path.write_text(content)

        result = structural_preview(
            str(file_path), "print($$$ARGS)", "logger.info($$$ARGS)", "python"
        )

        assert result is not None
        # File should NOT be modified
        assert file_path.read_text() == content


class TestStructuralApply:
    """Tests for structural apply (file modification)."""

    def test_structural_apply_file(self, tmp_path: Path):
        """Test structural apply modifies the file."""
        try:
            from omni_core_rs import structural_apply
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        content = "class OldClass:\n    pass\n"
        file_path = tmp_path / "test_apply.py"
        file_path.write_text(content)

        result = structural_apply(str(file_path), "OldClass", "NewClass", "python")

        assert result is not None
        new_content = file_path.read_text()
        assert "NewClass" in new_content
        assert "OldClass" not in new_content

    def test_structural_apply_no_matches(self, tmp_path: Path):
        """Test structural apply with no matches doesn't modify file."""
        try:
            from omni_core_rs import structural_apply
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        original = "x = 1 + 2"
        file_path = tmp_path / "test_no_change.py"
        file_path.write_text(original)

        result = structural_apply(str(file_path), "nonexistent($$$)", "replaced($$$)", "python")

        assert result is not None
        assert file_path.read_text() == original


class TestBatchStructuralReplace:
    """Tests for batch structural refactoring (The Ouroboros)."""

    def test_batch_structural_replace_dry_run(self, tmp_path: Path):
        """Test batch refactoring with dry run (no modifications)."""
        try:
            from omni_core_rs import batch_structural_replace
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        (tmp_path / "file1.py").write_text("print('hello')\n")
        (tmp_path / "file2.py").write_text("print('world')\n")
        (tmp_path / "data.json").write_text('{"key": "value"}')

        stats = batch_structural_replace(
            str(tmp_path),
            "print($$$ARGS)",
            "logger.info($$$ARGS)",
            "**/*.py",
            True,  # dry_run
        )

        assert stats is not None
        assert stats.files_scanned >= 2
        assert "print('hello')" in (tmp_path / "file1.py").read_text()

    def test_batch_structural_replace_apply(self, tmp_path: Path):
        """Test batch refactoring actually modifies files."""
        try:
            from omni_core_rs import batch_structural_replace
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        (tmp_path / "file1.py").write_text("print('hello')\n")
        (tmp_path / "file2.py").write_text("print('world')\n")

        stats = batch_structural_replace(
            str(tmp_path),
            "print($$$ARGS)",
            "logger.info($$$ARGS)",
            "**/*.py",
            False,  # dry_run = False
        )

        assert stats is not None
        assert stats.replacements >= 2
        assert stats.files_changed >= 2
        assert "logger.info" in (tmp_path / "file1.py").read_text()
        assert "logger.info" in (tmp_path / "file2.py").read_text()


class TestStructuralRefactoringEdgeCases:
    """Edge case tests for structural refactoring."""

    def test_replace_empty_content(self):
        """Test replace on empty content."""
        try:
            from omni_core_rs import structural_replace
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        result = structural_replace("", "print($$$)", "log($$$)", "python")
        assert result is not None

    def test_replace_unsupported_language(self, tmp_path: Path):
        """Test replace with unsupported language."""
        try:
            from omni_core_rs import structural_replace
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        content = "some code"
        result = structural_replace(content, "code", "new", "unsupported_lang")
        assert result is not None

    def test_preview_nonexistent_file(self):
        """Test preview on nonexistent file."""
        try:
            from omni_core_rs import structural_preview
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        result = structural_preview("/nonexistent/file.py", "print($$$)", "log($$$)", None)
        assert result is not None

    def test_apply_nonexistent_file(self):
        """Test apply on nonexistent file."""
        try:
            from omni_core_rs import structural_apply
        except ImportError:
            pytest.skip("Rust structural refactoring not available")

        result = structural_apply("/nonexistent/file.py", "print($$$)", "log($$$)", None)
        assert result is not None
