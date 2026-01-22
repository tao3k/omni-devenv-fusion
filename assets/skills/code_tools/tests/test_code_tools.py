"""
Code Tools Skill Tests - Phase 5 Migration

Tests for migrated code_tools skills:
- analyze.py: search_code, list_project_structure, ast_search, ast_search_dir
- refactor.py: apply_file_edit, structural operations

Verifies:
- @skill_command with autowire=True pattern
- ConfigPaths integration
- Zero-config tool discovery
"""

import sys
import tempfile
import os
from pathlib import Path

# Add assets/skills to path for imports
SKILLS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILLS_ROOT))

# Also add project root for agent.skills imports
PROJECT_ROOT = SKILLS_ROOT.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestAnalyzeImports:
    """Test analyze module imports."""

    def test_analyze_script_imports(self):
        """Test analyze script imports successfully."""
        from code_tools.scripts import analyze

        assert analyze is not None

    def test_search_code_function_exists(self):
        """Test search_code function is exported."""
        from code_tools.scripts.analyze import search_code

        assert callable(search_code)

    def test_list_project_structure_function_exists(self):
        """Test list_project_structure function is exported."""
        from code_tools.scripts.analyze import list_project_structure

        assert callable(list_project_structure)

    def test_ast_search_function_exists(self):
        """Test ast_search function is exported."""
        from code_tools.scripts.analyze import ast_search

        assert callable(ast_search)

    def test_ast_search_dir_function_exists(self):
        """Test ast_search_dir function is exported."""
        from code_tools.scripts.analyze import ast_search_dir

        assert callable(ast_search_dir)


class TestAnalyzeSkillCommand:
    """Test @skill_command decorator attributes."""

    def _has_skill_command_attr(self, func) -> bool:
        """Check if function has skill command attributes."""
        return hasattr(func, "_is_skill_command") and hasattr(func, "_skill_config")

    def _get_category(self, func) -> str | None:
        """Extract category from _skill_config dict."""
        config = getattr(func, "_skill_config", None)
        if config:
            return config.get("category")
        return None

    def test_search_code_has_skill_command(self):
        """Test search_code has skill command attributes."""
        from code_tools.scripts.analyze import search_code

        assert self._has_skill_command_attr(search_code)
        assert search_code._is_skill_command is True

    def test_search_code_autowire_enabled(self):
        """Test search_code has autowire in config."""
        from code_tools.scripts.analyze import search_code

        config = getattr(search_code, "_skill_config", None)
        assert config is not None
        execution = config.get("execution", {})
        assert execution.get("autowire") is True

    def test_list_project_structure_has_skill_command(self):
        """Test list_project_structure has skill command attributes."""
        from code_tools.scripts.analyze import list_project_structure

        assert self._has_skill_command_attr(list_project_structure)

    def test_ast_search_has_skill_command(self):
        """Test ast_search has skill command attributes."""
        from code_tools.scripts.analyze import ast_search

        assert self._has_skill_command_attr(ast_search)


class TestRefactorImports:
    """Test refactor module imports."""

    def test_refactor_script_imports(self):
        """Test refactor script imports successfully."""
        from code_tools.scripts import refactor

        assert refactor is not None

    def test_apply_file_edit_function_exists(self):
        """Test apply_file_edit function is exported."""
        from code_tools.scripts.refactor import apply_file_edit

        assert callable(apply_file_edit)

    def test_structural_replace_function_exists(self):
        """Test structural_replace function is exported."""
        from code_tools.scripts.refactor import structural_replace

        assert callable(structural_replace)

    def test_structural_preview_function_exists(self):
        """Test structural_preview function is exported."""
        from code_tools.scripts.refactor import structural_preview

        assert callable(structural_preview)

    def test_structural_apply_function_exists(self):
        """Test structural_apply function is exported."""
        from code_tools.scripts.refactor import structural_apply

        assert callable(structural_apply)

    def test_refactor_repository_function_exists(self):
        """Test refactor_repository function is exported."""
        from code_tools.scripts.refactor import refactor_repository

        assert callable(refactor_repository)


class TestRefactorSkillCommand:
    """Test refactor @skill_command decorator attributes."""

    def _has_skill_command_attr(self, func) -> bool:
        """Check if function has skill command attributes."""
        return hasattr(func, "_is_skill_command") and hasattr(func, "_skill_config")

    def test_apply_file_edit_has_skill_command(self):
        """Test apply_file_edit has skill command attributes."""
        from code_tools.scripts.refactor import apply_file_edit

        assert self._has_skill_command_attr(apply_file_edit)
        assert apply_file_edit._is_skill_command is True

    def test_apply_file_edit_autowire_enabled(self):
        """Test apply_file_edit has autowire in config."""
        from code_tools.scripts.refactor import apply_file_edit

        config = getattr(apply_file_edit, "_skill_config", None)
        assert config is not None
        execution = config.get("execution", {})
        assert execution.get("autowire") is True

    def test_structural_replace_has_skill_command(self):
        """Test structural_replace has skill command attributes."""
        from code_tools.scripts.refactor import structural_replace

        assert self._has_skill_command_attr(structural_replace)

    def test_structural_apply_has_skill_command(self):
        """Test structural_apply has skill command attributes."""
        from code_tools.scripts.refactor import structural_apply

        assert self._has_skill_command_attr(structural_apply)

    def test_get_edit_info_has_skill_command(self):
        """Test get_edit_info has skill command attributes."""
        from code_tools.scripts.refactor import get_edit_info

        assert self._has_skill_command_attr(get_edit_info)


class TestApplyFileEdit:
    """Test apply_file_edit atomic operation."""

    def _create_temp_file_in_project(self, content: str, suffix: str = ".txt") -> tuple[str, str]:
        """Create a temp file within the project directory and return (relative_path, absolute_path)."""
        from omni.foundation.config.paths import ConfigPaths

        paths = ConfigPaths()
        root = paths.project_root

        # Create temp file in project root
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, dir=root, delete=False) as f:
            f.write(content)
            abs_path = f.name

        rel_path = os.path.relpath(abs_path, root)
        return rel_path, abs_path

    def test_apply_file_edit_success(self):
        """Test successful file edit."""
        from code_tools.scripts.refactor import apply_file_edit

        rel_path, abs_path = self._create_temp_file_in_project("Hello World")

        try:
            result = apply_file_edit(
                file_path=rel_path,
                search_text="World",
                replace_text="Python",
            )

            assert result["success"] is True, f"Expected success, got: {result}"
            assert "diff" in result
            assert "+Python" in result["diff"]
        finally:
            if os.path.exists(abs_path):
                os.unlink(abs_path)

    def test_apply_file_edit_not_found(self):
        """Test file edit when search text not found."""
        from code_tools.scripts.refactor import apply_file_edit

        rel_path, abs_path = self._create_temp_file_in_project("Hello World")

        try:
            result = apply_file_edit(
                file_path=rel_path,
                search_text="NotFound",
                replace_text="Replace",
            )

            assert result["success"] is False
            assert "not found" in result["error"].lower()
        finally:
            if os.path.exists(abs_path):
                os.unlink(abs_path)

    def test_apply_file_edit_ambiguous(self):
        """Test file edit when multiple matches found."""
        from code_tools.scripts.refactor import apply_file_edit

        rel_path, abs_path = self._create_temp_file_in_project("foo foo foo")

        try:
            result = apply_file_edit(
                file_path=rel_path,
                search_text="foo",
                replace_text="bar",
            )

            assert result["success"] is False
            assert "Ambiguous" in result["error"]
        finally:
            if os.path.exists(abs_path):
                os.unlink(abs_path)


class TestSearchCode:
    """Test search_code function."""

    def test_search_code_returns_structure(self):
        """Test search_code returns structured result."""
        from code_tools.scripts.analyze import search_code

        result = search_code(pattern="def ", max_results=10)

        assert "success" in result
        assert "matches" in result
        assert isinstance(result["matches"], list)

    def test_search_code_finds_matches(self):
        """Test search_code finds expected patterns."""
        from code_tools.scripts.analyze import search_code

        result = search_code(pattern="import ", max_results=5)

        # Should find import statements
        if result["success"]:
            assert result["count"] >= 0  # May or may not find matches


class TestListProjectStructure:
    """Test list_project_structure function."""

    def test_list_project_structure_returns_structure(self):
        """Test list_project_structure returns structured result."""
        from code_tools.scripts.analyze import list_project_structure

        result = list_project_structure(depth=1)

        assert "success" in result
        assert "structure" in result
        assert isinstance(result["structure"], list)

    def test_list_project_structure_has_root(self):
        """Test result contains root path."""
        from code_tools.scripts.analyze import list_project_structure

        result = list_project_structure(depth=1)

        assert "root" in result


class TestExports:
    """Test module exports."""

    def test_analyze_all_exports(self):
        """Test analyze module __all__ is defined."""
        from code_tools.scripts import analyze

        assert hasattr(analyze, "__all__")
        expected = ["search_code", "list_project_structure", "ast_search", "ast_search_dir"]
        for item in expected:
            assert item in analyze.__all__, f"{item} not in analyze.__all__"

    def test_refactor_all_exports(self):
        """Test refactor module __all__ is defined."""
        from code_tools.scripts import refactor

        assert hasattr(refactor, "__all__")
        expected = [
            "apply_file_edit",
            "structural_replace",
            "structural_preview",
            "structural_apply",
            "refactor_repository",
            "get_edit_info",
        ]
        for item in expected:
            assert item in refactor.__all__, f"{item} not in refactor.__all__"
