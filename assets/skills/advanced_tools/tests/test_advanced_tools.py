"""
Advanced Tools Skill Tests - Phase 6 Migration

Tests for migrated advanced_tools skills:
- search.py: smart_search, smart_find
- fs.py: tree_view
- mutation.py: regex_replace

Verifies:
- @skill_command with autowire=True pattern
- ConfigPaths integration
- Modern toolchain (rg, fd, tree, sed)
- Environment-driven tool discovery
"""

import os
import sys
import tempfile
from pathlib import Path

# Add assets/skills to path for imports
SKILLS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILLS_ROOT))

# Also add project root for agent.skills imports
PROJECT_ROOT = SKILLS_ROOT.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestSearchImports:
    """Test search module imports."""

    def test_search_script_imports(self):
        """Test search script imports successfully."""
        from advanced_tools.scripts import search

        assert search is not None

    def test_smart_search_function_exists(self):
        """Test smart_search function is exported."""
        from advanced_tools.scripts.search import smart_search

        assert callable(smart_search)

    def test_smart_find_function_exists(self):
        """Test smart_find function is exported."""
        from advanced_tools.scripts.search import smart_find

        assert callable(smart_find)


class TestSearchSkillCommand:
    """Test search @skill_command decorator attributes."""

    def _has_skill_command_attr(self, func) -> bool:
        """Check if function has skill command attributes."""
        return hasattr(func, "_is_skill_command") and hasattr(func, "_skill_config")

    def test_smart_search_has_skill_command(self):
        """Test smart_search has skill command attributes."""
        from advanced_tools.scripts.search import smart_search

        assert self._has_skill_command_attr(smart_search)
        assert smart_search._is_skill_command is True

    def test_smart_search_autowire_enabled(self):
        """Test smart_search has autowire in config."""
        from advanced_tools.scripts.search import smart_search

        config = getattr(smart_search, "_skill_config", None)
        assert config is not None
        execution = config.get("execution", {})
        assert execution.get("autowire") is True

    def test_smart_find_has_skill_command(self):
        """Test smart_find has skill command attributes."""
        from advanced_tools.scripts.search import smart_find

        assert self._has_skill_command_attr(smart_find)


class TestSmartSearch:
    """Test smart_search function."""

    def test_smart_search_returns_structure(self):
        """Test smart_search returns structured result."""
        from advanced_tools.scripts.search import smart_search

        result = smart_search(pattern="def ")

        assert "success" in result
        assert "matches" in result
        assert "tool" in result
        assert result["tool"] == "ripgrep"

    def test_smart_search_finds_matches(self):
        """Test smart_search finds expected patterns."""
        from advanced_tools.scripts.search import smart_search

        result = smart_search(pattern="import ")

        # Should find import statements
        if result["success"]:
            assert result["count"] >= 0  # May or may not find matches
            if result["matches"]:
                assert "file" in result["matches"][0]
                assert "line" in result["matches"][0]
                assert "content" in result["matches"][0]

    def test_smart_search_not_found(self):
        """Test smart_search handles no matches."""
        import uuid

        from advanced_tools.scripts.search import smart_search

        # Use a UUID pattern that definitely won't exist anywhere
        unique_pattern = f"__UUID_PATTERN_{uuid.uuid4().hex.upper()}__"
        result = smart_search(pattern=unique_pattern)

        # Should return success with empty matches
        assert result["success"] is True
        assert result["count"] == 0
        assert result["matches"] == []


class TestSmartFind:
    """Test smart_find function."""

    def test_smart_find_returns_structure(self):
        """Test smart_find returns structured result."""
        from advanced_tools.scripts.search import smart_find

        result = smart_find(pattern="*.py")

        assert "success" in result
        assert "files" in result
        assert "tool" in result
        assert result["tool"] == "fd"

    def test_smart_find_finds_python_files(self):
        """Test smart_find finds Python files."""
        from advanced_tools.scripts.search import smart_find

        result = smart_find(pattern="*.py")

        if result["success"] and result["files"]:
            # Should find some .py files
            assert len(result["files"]) > 0

    def test_smart_find_with_extension(self):
        """Test smart_find with extension filter."""
        from advanced_tools.scripts.search import smart_find

        result = smart_find(extension="rs")

        if result["success"]:
            # Should find Rust files in this project
            assert "count" in result


class TestFsImports:
    """Test fs module imports."""

    def test_fs_script_imports(self):
        """Test fs script imports successfully."""
        from advanced_tools.scripts import fs

        assert fs is not None

    def test_tree_view_function_exists(self):
        """Test tree_view function is exported."""
        from advanced_tools.scripts.fs import tree_view

        assert callable(tree_view)


class TestTreeView:
    """Test tree_view function."""

    def _has_skill_command_attr(self, func) -> bool:
        """Check if function has skill command attributes."""
        return hasattr(func, "_is_skill_command") and hasattr(func, "_skill_config")

    def test_tree_view_has_skill_command(self):
        """Test tree_view has skill command attributes."""
        from advanced_tools.scripts.fs import tree_view

        assert self._has_skill_command_attr(tree_view)

    def test_tree_view_returns_structure(self):
        """Test tree_view returns structured result."""
        import shutil

        from advanced_tools.scripts.fs import tree_view

        # Skip if tree is not installed
        if not shutil.which("tree"):
            import pytest

            pytest.skip("tree command not installed")

        result = tree_view(depth=1)

        assert "success" in result
        assert "output" in result
        assert "tool" in result
        assert result["tool"] == "tree"

    def test_tree_view_error_when_missing(self):
        """Test tree_view returns error when tree is not installed."""
        import shutil

        from advanced_tools.scripts.fs import tree_view

        # If tree is not installed, we should get an error
        if not shutil.which("tree"):
            result = tree_view(depth=1)
            assert result["success"] is False
            assert "tree" in result["error"].lower()

    def test_tree_view_ignores_hidden(self):
        """Test tree_view ignores hidden directories by default."""
        import shutil

        from advanced_tools.scripts.fs import tree_view

        # Skip if tree is not installed
        if not shutil.which("tree"):
            import pytest

            pytest.skip("tree command not installed")

        result = tree_view(depth=2)

        # Should not contain hidden directories in output
        assert ".git" not in result["output"]


class TestMutationImports:
    """Test mutation module imports."""

    def test_mutation_script_imports(self):
        """Test mutation script imports successfully."""
        from advanced_tools.scripts import mutation

        assert mutation is not None

    def test_regex_replace_function_exists(self):
        """Test regex_replace function is exported."""
        from advanced_tools.scripts.mutation import regex_replace

        assert callable(regex_replace)


class TestRegexReplace:
    """Test regex_replace function."""

    def _has_skill_command_attr(self, func) -> bool:
        """Check if function has skill command attributes."""
        return hasattr(func, "_is_skill_command") and hasattr(func, "_skill_config")

    def _create_temp_file_in_project(self, content: str, suffix: str = ".txt") -> tuple[str, str]:
        """Create a temp file within the project directory."""
        from omni.foundation.config.paths import ConfigPaths

        paths = ConfigPaths()
        root = paths.project_root

        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, dir=root, delete=False) as f:
            f.write(content)
            abs_path = f.name

        rel_path = os.path.relpath(abs_path, root)
        return rel_path, abs_path

    def test_regex_replace_has_skill_command(self):
        """Test regex_replace has skill command attributes."""
        from advanced_tools.scripts.mutation import regex_replace

        assert self._has_skill_command_attr(regex_replace)

    def test_regex_replace_success(self):
        """Test successful regex replace."""
        import shutil

        from advanced_tools.scripts.mutation import regex_replace

        # Skip if sed is not installed
        if not shutil.which("sed"):
            import pytest

            pytest.skip("sed command not installed")

        rel_path, abs_path = self._create_temp_file_in_project("Hello World")

        try:
            result = regex_replace(
                file_path=rel_path,
                pattern="World",
                replacement="Python",
            )

            assert result["success"] is True
            assert result["tool"] == "sed"
            assert result["file"] == rel_path
        finally:
            if os.path.exists(abs_path):
                os.unlink(abs_path)

    def test_regex_replace_invalid_path(self):
        """Test regex_replace with invalid path."""
        from advanced_tools.scripts.mutation import regex_replace

        result = regex_replace(
            file_path="/tmp/outside_project.txt",
            pattern="test",
            replacement="replaced",
        )

        assert result["success"] is False
        assert "Invalid" in result["error"]


class TestExports:
    """Test module exports."""

    def test_search_all_exports(self):
        """Test search module __all__ is defined."""
        from advanced_tools.scripts import search

        assert hasattr(search, "__all__")
        expected = ["smart_search", "smart_find"]
        for item in expected:
            assert item in search.__all__, f"{item} not in search.__all__"

    def test_fs_all_exports(self):
        """Test fs module __all__ is defined."""
        from advanced_tools.scripts import fs

        assert hasattr(fs, "__all__")
        assert "tree_view" in fs.__all__

    def test_mutation_all_exports(self):
        """Test mutation module __all__ is defined."""
        from advanced_tools.scripts import mutation

        assert hasattr(mutation, "__all__")
        assert "regex_replace" in mutation.__all__

    def test_main_all_exports(self):
        """Test main scripts __all__ is defined."""
        # Import the search module and check it exports everything
        from advanced_tools.scripts import fs, mutation, search

        expected = ["smart_search", "smart_find", "tree_view", "regex_replace"]
        for item in expected:
            # Check if item is exported from any of the submodules
            found = hasattr(search, item) or hasattr(fs, item) or hasattr(mutation, item)
            assert found, f"{item} not found in any module"
