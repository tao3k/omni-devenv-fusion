"""
QA Skills Tests - Phase 7 Migration

Tests for migrated testing and knowledge skills:
- testing/scripts/pytest.py: run_pytest, list_tests
- knowledge/scripts/search_docs.py: search_documentation, search_standards

Verifies:
- @skill_command with autowire=True pattern
- ConfigPaths integration
- Environment-driven tool discovery
- Security sandboxing
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add assets/skills to path for imports
SKILLS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILLS_ROOT))


class TestPytestImports:
    """Test pytest module imports."""

    def test_pytest_script_imports(self):
        """Test pytest module imports successfully."""
        from testing.scripts import pytest as pytest_module

        assert pytest_module is not None

    def test_run_pytest_function_exists(self):
        """Test run_pytest function is exported."""
        from testing.scripts.pytest import run_pytest

        assert callable(run_pytest)

    def test_list_tests_function_exists(self):
        """Test list_tests function is exported."""
        from testing.scripts.pytest import list_tests

        assert callable(list_tests)


class TestPytestSkillCommand:
    """Test pytest @skill_command decorator attributes."""

    def _has_skill_command_attr(self, func) -> bool:
        """Check if function has skill command attributes."""
        return hasattr(func, "_is_skill_command") and hasattr(func, "_skill_config")

    def test_run_pytest_has_skill_command(self):
        """Test run_pytest has skill command attributes."""
        from testing.scripts.pytest import run_pytest

        assert self._has_skill_command_attr(run_pytest)
        assert run_pytest._is_skill_command is True

    def test_run_pytest_autowire_enabled(self):
        """Test run_pytest has autowire in config."""
        from testing.scripts.pytest import run_pytest

        config = getattr(run_pytest, "_skill_config", None)
        assert config is not None
        execution = config.get("execution", {})
        assert execution.get("autowire") is True

    def test_list_tests_has_skill_command(self):
        """Test list_tests has skill command attributes."""
        from testing.scripts.pytest import list_tests

        assert self._has_skill_command_attr(list_tests)


class TestRunPytest:
    """Test run_pytest function."""

    def test_run_pytest_returns_structure(self):
        """Test run_pytest returns structured result with mocked subprocess."""
        from unittest.mock import MagicMock, patch

        from testing.scripts.pytest import run_pytest

        # Mock subprocess.run to avoid actual pytest execution
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "1 passed in 0.01s\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = run_pytest(target="assets/skills/testing/tests/test_qa_skills.py")

        assert "success" in result
        assert "target" in result
        assert "summary" in result
        assert result["success"] is True

    def test_run_pytest_security_sandbox(self):
        """Test run_pytest cannot escape project root."""
        from testing.scripts.pytest import run_pytest

        from omni.foundation.config.paths import ConfigPaths

        # Create mock ConfigPaths
        mock_paths = MagicMock(spec=ConfigPaths)
        mock_paths.project_root = Path("/fake/root")

        result = run_pytest(target="../outside", paths=mock_paths)

        assert result["success"] is False
        assert "Access denied" in result["error"]

    def test_run_pytest_missing_pytest(self):
        """Test run_pytest returns error when pytest missing."""
        from testing.scripts.pytest import run_pytest

        with patch("shutil.which", return_value=None):
            result = run_pytest(target=".")

            assert result["success"] is False
            assert "pytest not found" in result["error"]

    def test_run_pytest_invalid_path(self):
        """Test run_pytest with non-existent path."""
        from testing.scripts.pytest import run_pytest

        result = run_pytest(target="/nonexistent/path/xyz")

        # Should either fail on security check or pytest execution
        assert result["success"] is False or "error" in result


class TestListTests:
    """Test list_tests function."""

    def test_list_tests_returns_structure(self):
        """Test list_tests returns structured result with mocked subprocess."""
        from unittest.mock import MagicMock, patch

        from testing.scripts.pytest import list_tests

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "test_example.py::test_example PASSED\n"

        with patch("subprocess.run", return_value=mock_result):
            result = list_tests(target="assets/skills/testing")

        assert "success" in result
        assert "target" in result
        assert "count" in result
        assert "tests" in result

    def test_list_tests_security_sandbox(self):
        """Test list_tests cannot escape project root."""
        from testing.scripts.pytest import list_tests

        from omni.foundation.config.paths import ConfigPaths

        mock_paths = MagicMock(spec=ConfigPaths)
        mock_paths.project_root = Path("/fake/root")

        result = list_tests(target="../outside", paths=mock_paths)

        assert result["success"] is False
        assert "Access denied" in result["error"]


class TestSearchDocsImports:
    """Test search_docs module imports."""

    def test_search_docs_script_imports(self):
        """Test search_docs module imports successfully."""
        from knowledge.scripts import search_docs

        assert search_docs is not None

    def test_search_documentation_function_exists(self):
        """Test search_documentation function is exported."""
        from knowledge.scripts.search_docs import search_documentation

        assert callable(search_documentation)

    def test_search_standards_function_exists(self):
        """Test search_standards function is exported."""
        from knowledge.scripts.search_docs import search_standards

        assert callable(search_standards)


class TestSearchDocsSkillCommand:
    """Test search_docs @skill_command decorator attributes."""

    def _has_skill_command_attr(self, func) -> bool:
        """Check if function has skill command attributes."""
        return hasattr(func, "_is_skill_command") and hasattr(func, "_skill_config")

    def test_search_documentation_has_skill_command(self):
        """Test search_documentation has skill command attributes."""
        from knowledge.scripts.search_docs import search_documentation

        assert self._has_skill_command_attr(search_documentation)
        assert search_documentation._is_skill_command is True

    def test_search_documentation_autowire_enabled(self):
        """Test search_documentation has autowire in config."""
        from knowledge.scripts.search_docs import search_documentation

        config = getattr(search_documentation, "_skill_config", None)
        assert config is not None
        execution = config.get("execution", {})
        assert execution.get("autowire") is True


class TestSearchDocumentation:
    """Test search_documentation function."""

    def test_search_documentation_returns_structure(self):
        """Test search_documentation returns structured result with mocked rg."""
        import json
        from unittest.mock import MagicMock, patch

        from knowledge.scripts.search_docs import search_documentation

        # Mock ripgrep JSON output
        fake_output = (
            json.dumps(
                {
                    "type": "match",
                    "data": {
                        "path": {"text": "docs/test.md"},
                        "line_number": 10,
                        "lines": {"text": "This is a python example"},
                    },
                }
            )
            + "\n"
        )

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (fake_output, "")
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            result = search_documentation(query="python")

        assert "success" in result
        assert "query" in result
        assert "count" in result
        assert "results" in result

    def test_search_documentation_no_rg(self):
        """Test search_documentation returns error when rg missing."""
        import shutil

        from knowledge.scripts import search_docs

        # Temporarily hide rg
        original_which = shutil.which
        try:
            shutil.which = lambda x: None if x == "rg" else original_which(x)
            result = search_docs.search_documentation(query="test")

            assert result["success"] is False
            assert "ripgrep" in result["error"].lower()
        finally:
            shutil.which = original_which

    def test_search_documentation_empty_query(self):
        """Test search_documentation with empty results (mocked)."""
        from unittest.mock import MagicMock, patch

        from knowledge.scripts.search_docs import search_documentation

        # Mock empty ripgrep output
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "")
        mock_proc.returncode = 1  # rg returns 1 when no matches

        with patch("subprocess.Popen", return_value=mock_proc):
            result = search_documentation(query="__UNIQUE_PATTERN_XYZ__")

        assert result["success"] is True
        assert result["count"] == 0


class TestSearchStandards:
    """Test search_standards function."""

    def test_search_standards_returns_structure(self):
        """Test search_standards returns structured result with mocked rg."""
        import json
        from unittest.mock import MagicMock, patch

        from knowledge.scripts.search_docs import search_standards

        # Mock ripgrep JSON output
        fake_output = (
            json.dumps(
                {
                    "type": "match",
                    "data": {
                        "path": {"text": "docs/reference/style.md"},
                        "line_number": 5,
                        "lines": {"text": "Follow PEP 8 style guide"},
                    },
                }
            )
            + "\n"
        )

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (fake_output, "")
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            result = search_standards(topic="style")

        assert "success" in result
        assert "topic" in result
        assert "results" in result

    def test_search_standards_missing_ref_dir(self):
        """Test search_standards when docs/reference/ missing."""
        from knowledge.scripts.search_docs import search_standards

        from omni.foundation.config.paths import ConfigPaths

        mock_paths = MagicMock(spec=ConfigPaths)
        mock_paths.project_root = Path("/tmp")  # No docs/reference

        with patch("shutil.which", return_value="/bin/rg"):
            result = search_standards(topic="test", paths=mock_paths)

            assert result["success"] is False
            assert "docs/reference/" in result["error"]


class TestExports:
    """Test module exports."""

    def test_testing_all_exports(self):
        """Test testing scripts __all__ is defined."""
        from testing.scripts import pytest as pytest_module

        assert hasattr(pytest_module, "__all__")
        expected = ["run_pytest", "list_tests"]
        for item in expected:
            assert item in pytest_module.__all__, f"{item} not in __all__"

    def test_knowledge_all_exports(self):
        """Test knowledge scripts __all__ is defined."""
        from knowledge.scripts import search_docs

        assert hasattr(search_docs, "__all__")
        expected = ["search_documentation", "search_standards"]
        for item in expected:
            assert item in search_docs.__all__, f"{item} not in __all__"
