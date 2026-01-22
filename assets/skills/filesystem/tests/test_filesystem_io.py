"""
Filesystem Skill Tests - Trinity Architecture v2.0

Tests for filesystem skill commands.
Verifies:
- @skill_command with autowire=True pattern
- ConfigPaths integration
- Path safety utilities
"""

import sys
from pathlib import Path

# Add assets/skills to path for imports
SKILLS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILLS_ROOT))

# Also add project root for agent.skills imports
PROJECT_ROOT = SKILLS_ROOT.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestFilesystemImports:
    """Test filesystem skill scripts can be imported."""

    def test_io_script_imports(self):
        """Test io script imports successfully."""
        from filesystem.scripts import io as io_module

        assert io_module is not None

    def test_read_file_function_exists(self):
        """Test read_file function is exported."""
        from filesystem.scripts.io import read_file

        assert callable(read_file)

    def test_save_file_function_exists(self):
        """Test save_file function is exported."""
        from filesystem.scripts.io import save_file

        assert callable(save_file)

    def test_write_file_function_exists(self):
        """Test write_file function is exported."""
        from filesystem.scripts.io import write_file

        assert callable(write_file)

    def test_list_directory_function_exists(self):
        """Test list_directory function is exported."""
        from filesystem.scripts.io import list_directory

        assert callable(list_directory)

    def test_get_file_info_function_exists(self):
        """Test get_file_info function is exported."""
        from filesystem.scripts.io import get_file_info

        assert callable(get_file_info)

    def test_apply_file_changes_function_exists(self):
        """Test apply_file_changes function is exported."""
        from filesystem.scripts.io import apply_file_changes

        assert callable(apply_file_changes)

    def test_file_operation_model_exists(self):
        """Test FileOperation model is exported."""
        from filesystem.scripts.io import FileOperation

        assert FileOperation is not None


class TestFilesystemExports:
    """Test filesystem skill exports."""

    def test_all_exports_defined(self):
        """Test __all__ contains expected items."""
        from filesystem.scripts import io

        expected = [
            "read_file",
            "save_file",
            "apply_file_changes",
            "list_directory",
            "write_file",
            "get_file_info",
            "FileOperation",
        ]
        for item in expected:
            assert item in io.__all__, f"{item} not in __all__"


class TestFileOperationModel:
    """Test FileOperation pydantic model."""

    def test_file_operation_create(self):
        """Test creating a FileOperation instance."""
        from filesystem.scripts.io import FileOperation

        op = FileOperation(
            action="write",
            path="test.txt",
            content="hello world",
        )
        assert op.action == "write"
        assert op.path == "test.txt"
        assert op.content == "hello world"

    def test_file_operation_with_search(self):
        """Test creating a FileOperation with search_for."""
        from filesystem.scripts.io import FileOperation

        op = FileOperation(
            action="replace",
            path="test.txt",
            content="new content",
            search_for="old content",
        )
        assert op.search_for == "old content"


class TestSkillCommandDecorator:
    """Test @skill_command decorator attributes."""

    def _get_category(self, func) -> str | None:
        """Extract category from _skill_config dict."""
        config = getattr(func, "_skill_config", None)
        if config:
            return config.get("category")
        return None

    def _has_skill_command_attr(self, func) -> bool:
        """Check if function has skill command attributes."""
        return hasattr(func, "_is_skill_command") and hasattr(func, "_skill_config")

    def test_read_file_has_skill_command_attr(self):
        """Test read_file has _is_skill_command and _skill_config attributes."""
        from filesystem.scripts.io import read_file

        assert self._has_skill_command_attr(read_file)
        assert read_file._is_skill_command is True

    def test_read_file_autowire_enabled(self):
        """Test read_file has autowire configuration in _skill_config."""
        from filesystem.scripts.io import read_file

        config = getattr(read_file, "_skill_config", None)
        assert config is not None
        execution = config.get("execution", {})
        assert execution.get("autowire") is True

    def test_read_file_category_read(self):
        """Test read_file has category 'read'."""
        from filesystem.scripts.io import read_file

        assert self._get_category(read_file) == "read"

    def test_save_file_has_skill_command_attr(self):
        """Test save_file has _is_skill_command and _skill_config attributes."""
        from filesystem.scripts.io import save_file

        assert self._has_skill_command_attr(save_file)
        assert save_file._is_skill_command is True

    def test_save_file_category_write(self):
        """Test save_file has category 'write'."""
        from filesystem.scripts.io import save_file

        assert self._get_category(save_file) == "write"

    def test_list_directory_has_skill_command_attr(self):
        """Test list_directory has _is_skill_command and _skill_config attributes."""
        from filesystem.scripts.io import list_directory

        assert self._has_skill_command_attr(list_directory)
        assert list_directory._is_skill_command is True

    def test_list_directory_category_read(self):
        """Test list_directory has category 'read'."""
        from filesystem.scripts.io import list_directory

        assert self._get_category(list_directory) == "read"

    def test_write_file_has_skill_command_attr(self):
        """Test write_file has _is_skill_command and _skill_config attributes."""
        from filesystem.scripts.io import write_file

        assert self._has_skill_command_attr(write_file)
        assert write_file._is_skill_command is True

    def test_get_file_info_has_skill_command_attr(self):
        """Test get_file_info has _is_skill_command and _skill_config attributes."""
        from filesystem.scripts.io import get_file_info

        assert self._has_skill_command_attr(get_file_info)
        assert get_file_info._is_skill_command is True

    def test_get_file_info_category_read(self):
        """Test get_file_info has category 'read'."""
        from filesystem.scripts.io import get_file_info

        assert self._get_category(get_file_info) == "read"

    def test_apply_file_changes_has_skill_command_attr(self):
        """Test apply_file_changes has _is_skill_command and _skill_config attributes."""
        from filesystem.scripts.io import apply_file_changes

        assert self._has_skill_command_attr(apply_file_changes)
        assert apply_file_changes._is_skill_command is True
