"""
Tests for structural_editing skill (Phase 52: The Surgeon).

Tests for AST-based code modification using omni-core-rs Rust bindings.
Implements the "Surgical Precision" philosophy with dry-run capability.

Covers:
1. Unit tests for replace (content-based operations)
2. Integration tests for preview/apply (file-based operations)
3. Multi-language support (Python, Rust, JavaScript, TypeScript)
4. Pattern syntax variations ($NAME, $$, $$$ARGS)
5. Error handling and edge cases
6. Dry-run verification (preview does not modify files)
7. Skill registration and command availability
"""

import pytest
import tempfile
import os
from pathlib import Path


def _get_structural_skill():
    """Load and return structural_editing skill."""
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()
    if not manager._loaded:
        manager.load_all()

    return manager.skills.get("structural_editing")


class TestStructuralReplace:
    """Unit tests for replace (content-based operations)."""

    def test_simple_function_rename_python(self):
        """Test renaming a function in Python content."""
        import omni_core_rs

        content = "x = old_function(arg1, arg2)"
        result = omni_core_rs.structural_replace(
            content, "old_function($$$ARGS)", "new_function($$$ARGS)", "python"
        )

        assert "new_function" in result
        assert "old_function" not in result or "Replacements: 1" in result

    def test_multiple_replacements_python(self):
        """Test multiple replacements in Python content."""
        import omni_core_rs

        content = """
def connect(a, b):
    result = connect(1, 2)
    data = connect(3, 4)
"""
        result = omni_core_rs.structural_replace(
            content, "connect($$$ARGS)", "safe_connect($$$ARGS)", "python"
        )

        # Should replace all 3 occurrences
        assert "Replacements: 3" in result or result.count("safe_connect") >= 2

    def test_class_rename_python(self):
        """Test renaming a class in Python content."""
        import omni_core_rs

        content = """
class OldClassName:
    pass

x = OldClassName()
y = OldClassName.method()
"""
        result = omni_core_rs.structural_replace(content, "OldClassName", "NewClassName", "python")

        assert "NewClassName" in result

    def test_rust_function_rename(self):
        """Test renaming a function in Rust content."""
        import omni_core_rs

        content = "let x = old_function(arg1, arg2);"
        result = omni_core_rs.structural_replace(
            content, "old_function($$$ARGS)", "new_function($$$ARGS)", "rust"
        )

        assert "new_function" in result

    def test_rust_struct_rename(self):
        """Test renaming a struct in Rust content."""
        import omni_core_rs

        content = """
pub struct OldName {
    field: i32,
}

let x = OldName { field: 1 };
"""
        result = omni_core_rs.structural_replace(
            content, "pub struct OldName", "pub struct NewName", "rust"
        )

        assert "NewName" in result
        assert "pub struct NewName" in result

    def test_javascript_function_rename(self):
        """Test renaming a function in JavaScript content."""
        import omni_core_rs

        content = "const x = oldFunc(a, b);"
        result = omni_core_rs.structural_replace(
            content, "oldFunc($$$ARGS)", "newFunc($$$ARGS)", "javascript"
        )

        assert "newFunc" in result

    def test_js_object_rename(self):
        """Test renaming in JavaScript content."""
        import omni_core_rs

        content = "const result = oldFunc(1, 2);"
        result = omni_core_rs.structural_replace(
            content, "oldFunc($$$ARGS)", "newFunc($$$ARGS)", "javascript"
        )

        assert "newFunc" in result

    def test_no_matches_returns_info(self):
        """Test that no matches returns informative message."""
        import omni_core_rs

        content = "x = 1 + 2"
        result = omni_core_rs.structural_replace(
            content, "nonexistent_pattern($$$)", "replacement($$$)", "python"
        )

        assert "No matches" in result or result.count == 0

    def test_error_handling_unsupported_language(self):
        """Test error handling for unsupported language."""
        import omni_core_rs

        content = "x = 1"
        result = omni_core_rs.structural_replace(content, "x", "y", "unsupported_language")

        assert "error" in result.lower() or "Error" in result


class TestStructuralPreview:
    """Integration tests for structural_preview (dry-run, no file modification)."""

    def test_preview_shows_diff(self):
        """Test that preview shows the diff that would be applied."""
        import omni_core_rs

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = old_api(data)")
            f.flush()
            temp_path = f.name

        try:
            result = omni_core_rs.structural_preview(temp_path, "old_api($$$)", "new_api($$$)")

            assert "Diff:" in result or "---" in result or "+" in result
            assert "old_api" in result or "old_api" in open(temp_path).read()
        finally:
            os.unlink(temp_path)

    def test_preview_does_not_modify_file(self):
        """Test that preview does NOT modify the file."""
        import omni_core_rs

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            original_content = "x = old_api(data)"
            f.write(original_content)
            f.flush()
            temp_path = f.name

        try:
            # Run preview
            omni_core_rs.structural_preview(temp_path, "old_api($$$)", "new_api($$$)")

            # Verify file is unchanged
            with open(temp_path) as f:
                content_after = f.read()

            assert content_after == original_content
            assert "old_api" in content_after
            assert "new_api" not in content_after
        finally:
            os.unlink(temp_path)

    def test_preview_with_language_hint(self):
        """Test preview with explicit language hint."""
        import omni_core_rs

        with tempfile.NamedTemporaryFile(mode="w", suffix=".rs", delete=False) as f:
            f.write("let x = old_fn(arg);")
            f.flush()
            temp_path = f.name

        try:
            result = omni_core_rs.structural_preview(
                temp_path, "old_fn($$$ARGS)", "new_fn($$$ARGS)", language="rust"
            )

            assert "Replacements:" in result
        finally:
            os.unlink(temp_path)

    def test_preview_no_matches(self):
        """Test preview when no matches are found."""
        import omni_core_rs

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1 + 2")
            f.flush()
            temp_path = f.name

        try:
            result = omni_core_rs.structural_preview(
                temp_path, "nonexistent($$$)", "replacement($$$)"
            )

            assert "No matches" in result
        finally:
            os.unlink(temp_path)


class TestStructuralApply:
    """Integration tests for structural_apply (actual file modification)."""

    def test_apply_modifies_file(self):
        """Test that apply actually modifies the file."""
        import omni_core_rs

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            original = "x = deprecated_call(value)"
            f.write(original)
            f.flush()
            temp_path = f.name

        try:
            result = omni_core_rs.structural_apply(
                temp_path, "deprecated_call($$$)", "modern_call($$$)"
            )

            assert "Replacements: 1" in result

            # Verify file is modified
            with open(temp_path) as f:
                content_after = f.read()

            assert "modern_call" in content_after
            assert "deprecated_call" not in content_after
            assert "[FILE MODIFIED]" in result
        finally:
            os.unlink(temp_path)

    def test_apply_multiple_replacements(self):
        """Test applying multiple replacements."""
        import omni_core_rs

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("old_fn(1)\nold_fn(2)\nold_fn(3)")
            f.flush()
            temp_path = f.name

        try:
            result = omni_core_rs.structural_apply(temp_path, "old_fn($$$ARGS)", "new_fn($$$ARGS)")

            assert "Replacements: 3" in result

            with open(temp_path) as f:
                content = f.read()

            assert content.count("new_fn") == 3
            assert "old_fn" not in content
        finally:
            os.unlink(temp_path)


class TestDryRunWorkflow:
    """Test the full dry-run workflow (preview then apply)."""

    def test_dry_run_then_apply_workflow(self):
        """Test the complete workflow: preview -> verify -> apply."""
        import omni_core_rs

        # Use different names for function definition and calls
        test_content = """
def helper(x):
    return x * 2

result1 = old_api(10)
result2 = old_api(20)
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_content)
            f.flush()
            temp_path = f.name

        try:
            # Step 1: Dry run (preview)
            preview_result = omni_core_rs.structural_preview(
                temp_path, "old_api($$$)", "new_api($$$, debug=True)"
            )

            assert "Replacements: 2" in preview_result

            # Verify file is still unchanged
            with open(temp_path) as f:
                content_after_preview = f.read()

            assert "old_api" in content_after_preview
            assert "new_api" not in content_after_preview

            # Step 2: Apply changes
            apply_result = omni_core_rs.structural_apply(
                temp_path, "old_api($$$)", "new_api($$$, debug=True)"
            )

            # Verify file is now modified
            with open(temp_path) as f:
                content_after_apply = f.read()

            assert "new_api" in content_after_apply
            assert "debug=True" in content_after_apply
            # old_api calls should be gone (but helper function remains)
            assert "old_api(10)" not in content_after_apply
            assert "old_api(20)" not in content_after_apply

        finally:
            os.unlink(temp_path)


class TestPatternSyntax:
    """Test various pattern syntaxes."""

    def test_dollar_name_capture(self):
        """Test $NAME capture pattern."""
        import omni_core_rs

        content = "class MyClass:"
        result = omni_core_rs.structural_replace(content, "class $NAME", "class New$NAME", "python")

        assert "NewMyClass" in result

    def test_triple_dollar_variadic(self):
        """Test $$$ variadic capture pattern."""
        import omni_core_rs

        content = "process(a, b, c, d, e)"
        result = omni_core_rs.structural_replace(
            content, "process($$$)", "enhanced_process($$$)", "python"
        )

        assert "enhanced_process(a, b, c, d, e)" in result

    def test_named_variadic_capture(self):
        """Test $$$ARGS named variadic capture."""
        import omni_core_rs

        content = "func(x, y, z)"
        result = omni_core_rs.structural_replace(
            content, "func($$$ARGS)", "func_with_log($$$ARGS)", "python"
        )

        assert "func_with_log(x, y, z)" in result


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_empty_content(self):
        """Test handling of empty content."""
        import omni_core_rs

        result = omni_core_rs.structural_replace("", "x", "y", "python")
        assert "No matches" in result or result.count == 0

    def test_invalid_pattern(self):
        """Test handling of invalid ast-grep pattern."""
        import omni_core_rs

        content = "x = 1"
        # Invalid pattern (unbalanced parens) - ast-grep treats it as literal
        result = omni_core_rs.structural_replace(
            content,
            "func($",  # Invalid pattern - treated as literal
            "replacement",
            "python",
        )

        # Invalid patterns are treated as literals and return no matches
        assert "No matches" in result or result.count == 0

    def test_nonexistent_file(self):
        """Test handling of nonexistent file for preview/apply."""
        import omni_core_rs

        result = omni_core_rs.structural_preview(
            "/nonexistent/path/to/file.py", "pattern", "replacement"
        )

        assert "error" in result.lower() or "Error" in result or "not found" in result.lower()

    def test_binary_file_rejection(self):
        """Test that binary files are rejected by omni-io."""
        import omni_core_rs

        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"\x00\x01\x02\x03")
            f.flush()
            temp_path = f.name

        try:
            result = omni_core_rs.structural_preview(temp_path, "pattern", "replacement")

            # Should fail due to binary content detection
            assert "error" in result.lower() or "binary" in result.lower() or "Error" in result
        finally:
            os.unlink(temp_path)


class TestGetEditInfo:
    """Test get_edit_info function."""

    def test_get_edit_info_returns_dict(self):
        """Test that get_edit_info returns capability info."""
        skill = _get_structural_skill()
        assert skill is not None

        # Find get_edit_info command
        cmd = None
        for name, c in skill.commands.items():
            if name.endswith("_get_edit_info") or name == "get_edit_info":
                cmd = c
                break

        assert cmd is not None
        # The command is a function, call it
        result = cmd.func()
        assert isinstance(result, dict)
        assert result["name"] == "structural_editing"
        assert "rust_available" in result
        assert "supported_languages" in result
        assert "python" in result["supported_languages"]
        assert "rust" in result["supported_languages"]


class TestSkillRegistration:
    """Test skill loading and availability."""

    def test_structural_editing_skill_loaded(self):
        """Test that structural_editing skill can be loaded."""
        skill = _get_structural_skill()
        assert skill is not None

    def test_structural_editing_has_commands(self):
        """Test that structural_editing has expected commands."""
        skill = _get_structural_skill()
        assert skill is not None

        command_names = list(skill.commands.keys())
        assert len(command_names) >= 3

        # Check for key commands (registered via @skill_script name parameter)
        # Names are like "structural_editing_replace" -> displayed as "replace"
        command_names_str = " ".join(command_names)
        assert "replace" in command_names_str
        assert "preview" in command_names_str
        assert "apply" in command_names_str

    def test_commands_have_valid_schemas(self):
        """Verify all commands have valid input schemas."""
        skill = _get_structural_skill()
        assert skill is not None

        for cmd_name, cmd in skill.commands.items():
            assert isinstance(cmd.input_schema, dict)
            assert "properties" in cmd.input_schema
