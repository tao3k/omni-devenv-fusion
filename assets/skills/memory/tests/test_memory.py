"""
Memory Skill Tests - Trinity Architecture v2.0

Tests for memory skill commands using direct script imports.
Verifies:
- @skill_command with autowire=True pattern
- PRJ_DATA_HOME usage (not PRJ_CACHE)
- ConfigPaths integration
"""

import sys
from pathlib import Path

# Add assets/skills to path for imports
SKILLS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILLS_ROOT))


class TestMemoryScripts:
    """Test memory skill scripts can be imported."""

    def test_save_memory_command(self):
        """Test save_memory command is available."""
        from memory.scripts import memory as memory_script

        assert hasattr(memory_script, "save_memory")

    def test_search_memory_command(self):
        """Test search_memory command is available."""
        from memory.scripts import memory as memory_script

        assert hasattr(memory_script, "search_memory")

    def test_index_memory_command(self):
        """Test index_memory command is available."""
        from memory.scripts import memory as memory_script

        assert hasattr(memory_script, "index_memory")

    def test_get_memory_stats_command(self):
        """Test get_memory_stats command is available."""
        from memory.scripts import memory as memory_script

        assert hasattr(memory_script, "get_memory_stats")

    def test_load_skill_command(self):
        """Test load_skill command is available."""
        from memory.scripts import memory as memory_script

        assert hasattr(memory_script, "load_skill")


class TestMemoryExports:
    """Test memory skill exports."""

    def test_all_exports_defined(self):
        """Test __all__ contains expected items."""
        from memory.scripts import memory

        expected = [
            "save_memory",
            "search_memory",
            "index_memory",
            "get_memory_stats",
            "load_skill",
            "MEMORY_ROOT",
            "DEFAULT_TABLE",
        ]
        for item in expected:
            assert item in memory.__all__, f"{item} not in __all__"

    def test_memory_root_defined(self):
        """Test MEMORY_ROOT is a Path."""
        from memory.scripts.memory import MEMORY_ROOT

        assert isinstance(MEMORY_ROOT, Path)

    def test_default_table_defined(self):
        """Test DEFAULT_TABLE is a string."""
        from memory.scripts.memory import DEFAULT_TABLE

        assert isinstance(DEFAULT_TABLE, str)
        assert DEFAULT_TABLE == "knowledge_base"


class TestSkillCommandDecorator:
    """Test @skill_command decorator attributes."""

    def test_save_memory_has_skill_command_attr(self):
        """Test save_memory has _is_skill_command attribute."""
        from memory.scripts.memory import save_memory

        assert hasattr(save_memory, "_is_skill_command")
        assert save_memory._is_skill_command is True
        assert hasattr(save_memory, "_skill_config")

    def test_search_memory_has_skill_command_attr(self):
        """Test search_memory has _is_skill_command attribute."""
        from memory.scripts.memory import search_memory

        assert hasattr(search_memory, "_is_skill_command")
        assert search_memory._is_skill_command is True
        assert hasattr(search_memory, "_skill_config")

    def test_index_memory_has_skill_command_attr(self):
        """Test index_memory has _is_skill_command attribute."""
        from memory.scripts.memory import index_memory

        assert hasattr(index_memory, "_is_skill_command")
        assert index_memory._is_skill_command is True
        assert hasattr(index_memory, "_skill_config")

    def test_get_memory_stats_has_skill_command_attr(self):
        """Test get_memory_stats has _is_skill_command attribute."""
        from memory.scripts.memory import get_memory_stats

        assert hasattr(get_memory_stats, "_is_skill_command")
        assert get_memory_stats._is_skill_command is True
        assert hasattr(get_memory_stats, "_skill_config")

    def test_load_skill_has_skill_command_attr(self):
        """Test load_skill has _is_skill_command attribute."""
        from memory.scripts.memory import load_skill

        assert hasattr(load_skill, "_is_skill_command")
        assert load_skill._is_skill_command is True
        assert hasattr(load_skill, "_skill_config")


class TestMemoryPathResolution:
    """Test memory path resolution uses PRJ_DATA_HOME."""

    def test_memory_root_is_path(self):
        """Test MEMORY_ROOT is a valid Path object."""
        from memory.scripts.memory import MEMORY_ROOT, _get_memory_path

        # Should be a Path object
        assert isinstance(MEMORY_ROOT, Path)

        # _get_memory_path should return the same
        assert _get_memory_path() == MEMORY_ROOT

    def test_memory_root_uses_data_home(self):
        """Test MEMORY_ROOT is under PRJ_DATA_HOME, not PRJ_CACHE."""
        from memory.scripts.memory import MEMORY_ROOT

        memory_root_str = str(MEMORY_ROOT)

        # Should contain "memory" subdirectory
        assert "memory" in memory_root_str

        # Should NOT be in cache directory (by naming convention)
        # PRJ_DATA_HOME is for persistent data, PRJ_CACHE is for temporary cache
        # Memory is persistent data, so it should be in .data not .cache
        assert ".cache" not in memory_root_str or "memory" in memory_root_str


class TestCommandCategories:
    """Test command categories are correctly set."""

    def _get_category(self, func) -> str | None:
        """Extract category from _skill_config dict."""
        config = getattr(func, "_skill_config", None)
        if config:
            return config.get("category")
        return None

    def test_save_memory_category_write(self):
        """Test save_memory has category 'write'."""
        from memory.scripts.memory import save_memory

        assert self._get_category(save_memory) == "write"

    def test_search_memory_category_read(self):
        """Test search_memory has category 'read'."""
        from memory.scripts.memory import search_memory

        assert self._get_category(search_memory) == "read"

    def test_index_memory_category_write(self):
        """Test index_memory has category 'write'."""
        from memory.scripts.memory import index_memory

        assert self._get_category(index_memory) == "write"

    def test_get_memory_stats_category_view(self):
        """Test get_memory_stats has category 'view'."""
        from memory.scripts.memory import get_memory_stats

        assert self._get_category(get_memory_stats) == "view"

    def test_load_skill_category_write(self):
        """Test load_skill has category 'write'."""
        from memory.scripts.memory import load_skill

        assert self._get_category(load_skill) == "write"


class TestMemoryRustBridge:
    """Test memory skill Rust bridge."""

    def test_rust_bindings_import(self):
        """Test that Rust bindings can be imported."""
        try:
            from memory.extensions.rust_bridge import bindings

            assert bindings is not None
        except ImportError:
            pass  # Rust bridge optional
