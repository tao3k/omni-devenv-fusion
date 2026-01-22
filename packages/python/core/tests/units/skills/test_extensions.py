"""
test_extensions.py - Skill Extension System Tests

Tests for skill extension loading, fixtures, and wrapper system.

Usage:
    uv run pytest packages/python/core/tests/units/skills/test_extensions.py -v
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestSkillExtensionLoader:
    """Test the SkillExtensionLoader class."""

    def test_loader_initialization(self):
        """Test loader initializes correctly."""
        from omni.core.skills.extensions.loader import SkillExtensionLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = SkillExtensionLoader(tmpdir, "test_skill")

            assert loader.extension_path == Path(tmpdir)
            assert loader.skill_name == "test_skill"
            assert loader.extensions == {}
            assert loader._loaded is False

    def test_load_nonexistent_directory(self):
        """Test loading when extension directory doesn't exist."""
        from omni.core.skills.extensions.loader import SkillExtensionLoader

        loader = SkillExtensionLoader("/nonexistent/path/extensions", "test")
        loader.load_all()

        # Non-existent directory: _loaded stays False because we return early
        assert loader._loaded is False
        assert len(loader) == 0

    def test_load_single_file_extension(self):
        """Test loading a single-file extension."""
        from omni.core.skills.extensions.loader import (
            SkillExtensionLoader,
            reset_extension_stats,
        )

        reset_extension_stats()

        with tempfile.TemporaryDirectory() as tmpdir:
            ext_dir = Path(tmpdir) / "extensions"
            ext_dir.mkdir()

            # Create a simple extension file
            (ext_dir / "my_extension.py").write_text("""
EXTENSION_NAME = "my_extension"

def hello():
    return "Hello from extension"
""")

            loader = SkillExtensionLoader(ext_dir, "test_skill")
            loader.load_all()

            assert len(loader) == 1
            assert "my_extension" in loader.list_all()

    def test_load_package_extension(self):
        """Test loading a package-style extension."""
        from omni.core.skills.extensions.loader import (
            SkillExtensionLoader,
            reset_extension_stats,
        )

        reset_extension_stats()

        with tempfile.TemporaryDirectory() as tmpdir:
            ext_dir = Path(tmpdir) / "extensions"
            ext_dir.mkdir()

            # Create a package extension
            pkg_dir = ext_dir / "rust_bridge"
            pkg_dir.mkdir()
            (pkg_dir / "__init__.py").write_text("""
EXTENSION_NAME = "rust_bridge"

def fast_operation():
    return "Fast result"
""")

            loader = SkillExtensionLoader(ext_dir, "test_skill")
            loader.load_all()

            assert len(loader) == 1
            assert "rust_bridge" in loader.list_all()

    def test_skip_hidden_files(self):
        """Test that hidden files are skipped."""
        from omni.core.skills.extensions.loader import (
            SkillExtensionLoader,
            reset_extension_stats,
        )

        reset_extension_stats()

        with tempfile.TemporaryDirectory() as tmpdir:
            ext_dir = Path(tmpdir) / "extensions"
            ext_dir.mkdir()

            # Create hidden file
            (ext_dir / "_private.py").write_text("# Hidden")
            (ext_dir / "__pycache__").mkdir()

            loader = SkillExtensionLoader(ext_dir, "test_skill")
            loader.load_all()

            assert len(loader) == 0

    def test_get_extension(self):
        """Test getting an extension by name."""
        from omni.core.skills.extensions.loader import (
            SkillExtensionLoader,
            reset_extension_stats,
        )

        reset_extension_stats()

        with tempfile.TemporaryDirectory() as tmpdir:
            ext_dir = Path(tmpdir) / "extensions"
            ext_dir.mkdir()
            (ext_dir / "test_ext.py").write_text("TEST = True")

            loader = SkillExtensionLoader(ext_dir, "test")
            loader.load_all()

            ext = loader.get("test_ext")
            assert ext is not None

            missing = loader.get("nonexistent")
            assert missing is None

    def test_has_extension(self):
        """Test checking if extension exists."""
        from omni.core.skills.extensions.loader import (
            SkillExtensionLoader,
            reset_extension_stats,
        )

        reset_extension_stats()

        with tempfile.TemporaryDirectory() as tmpdir:
            ext_dir = Path(tmpdir) / "extensions"
            ext_dir.mkdir()
            (ext_dir / "test_ext.py").write_text("TEST = True")

            loader = SkillExtensionLoader(ext_dir, "test")
            loader.load_all()

            assert loader.has("test_ext") is True
            assert loader.has("nonexistent") is False

    def test_get_or_raise(self):
        """Test get_or_raise raises KeyError for missing extension."""
        from omni.core.skills.extensions.loader import (
            SkillExtensionLoader,
            reset_extension_stats,
        )

        reset_extension_stats()

        with tempfile.TemporaryDirectory() as tmpdir:
            ext_dir = Path(tmpdir) / "extensions"
            ext_dir.mkdir()

            loader = SkillExtensionLoader(ext_dir, "test")
            loader.load_all()

            with pytest.raises(KeyError):
                loader.get_or_raise("nonexistent")

    def test_iterate_extensions(self):
        """Test iterating over extension names."""
        from omni.core.skills.extensions.loader import (
            SkillExtensionLoader,
            reset_extension_stats,
        )

        reset_extension_stats()

        with tempfile.TemporaryDirectory() as tmpdir:
            ext_dir = Path(tmpdir) / "extensions"
            ext_dir.mkdir()
            (ext_dir / "ext1.py").write_text("")
            (ext_dir / "ext2.py").write_text("")

            loader = SkillExtensionLoader(ext_dir, "test")
            loader.load_all()

            names = list(loader)
            assert len(names) == 2
            assert "ext1" in names
            assert "ext2" in names

    def test_bool_false_when_empty(self):
        """Test loader evaluates to False when no extensions."""
        from omni.core.skills.extensions.loader import (
            SkillExtensionLoader,
            reset_extension_stats,
        )

        reset_extension_stats()

        with tempfile.TemporaryDirectory() as tmpdir:
            ext_dir = Path(tmpdir) / "extensions"
            ext_dir.mkdir()

            loader = SkillExtensionLoader(ext_dir, "test")
            loader.load_all()

            assert bool(loader) is False

    def test_bool_true_when_has_extensions(self):
        """Test loader evaluates to True when has extensions."""
        from omni.core.skills.extensions.loader import (
            SkillExtensionLoader,
            reset_extension_stats,
        )

        reset_extension_stats()

        with tempfile.TemporaryDirectory() as tmpdir:
            ext_dir = Path(tmpdir) / "extensions"
            ext_dir.mkdir()
            (ext_dir / "test.py").write_text("")

            loader = SkillExtensionLoader(ext_dir, "test")
            loader.load_all()

            assert bool(loader) is True


class TestExtensionWrapper:
    """Test the ExtensionWrapper class."""

    def test_wrapper_creation(self):
        """Test wrapper wraps a module correctly."""
        from omni.core.skills.extensions.wrapper import ExtensionWrapper

        mock_module = MagicMock()
        mock_module.__name__ = "test_extension"
        mock_module.test_func = MagicMock()

        wrapper = ExtensionWrapper(mock_module, "test_extension")

        assert wrapper.name == "test_extension"
        assert wrapper.module is mock_module

    def test_wrapper_getattr(self):
        """Test getting attributes from wrapped module."""
        from omni.core.skills.extensions.wrapper import ExtensionWrapper

        mock_module = MagicMock()
        mock_module.__name__ = "test_extension"
        mock_module.my_function = MagicMock(return_value="result")

        wrapper = ExtensionWrapper(mock_module, "test_extension")

        assert wrapper.my_function() == "result"

    def test_wrapper_hasattr(self):
        """Test hasattr on wrapper."""
        from omni.core.skills.extensions.wrapper import ExtensionWrapper

        mock_module = MagicMock()
        mock_module.__name__ = "test_extension"
        mock_module.existing_attr = True

        wrapper = ExtensionWrapper(mock_module, "test_extension")

        assert hasattr(wrapper, "existing_attr") is True
        # MagicMock returns True for any hasattr, so just test existing_attr
        # In real use, ExtensionWrapper delegates to module which would return False


class TestFixtureSystem:
    """Test the fixture system for extension injection."""

    def test_fixture_registry_register(self):
        """Test registering fixtures."""
        from omni.core.skills.extensions.fixtures import FixtureRegistry

        FixtureRegistry.clear()

        def my_impl():
            return "implemented"

        FixtureRegistry.register("test_ext", "my_func", my_impl)

        assert "test_ext" in FixtureRegistry._registry
        assert "my_func" in FixtureRegistry._registry["test_ext"]

    def test_fixture_registry_get(self):
        """Test getting registered fixtures."""
        from omni.core.skills.extensions.fixtures import FixtureRegistry

        FixtureRegistry.clear()

        def my_impl():
            return "result"

        FixtureRegistry.register("test_ext", "my_func", my_impl)

        result = FixtureRegistry.get("test_ext", "my_func")
        assert result() == "result"

    def test_fixture_registry_get_missing(self):
        """Test getting missing fixture returns None."""
        from omni.core.skills.extensions.fixtures import FixtureRegistry

        FixtureRegistry.clear()

        result = FixtureRegistry.get("nonexistent", "func")
        assert result is None

    def test_fixture_registry_clear(self):
        """Test clearing the registry."""
        from omni.core.skills.extensions.fixtures import FixtureRegistry

        FixtureRegistry.register("ext1", "func1", lambda: None)
        FixtureRegistry.register("ext2", "func2", lambda: None)

        FixtureRegistry.clear()

        assert len(FixtureRegistry._registry) == 0

    def test_fixture_registry_clear_specific(self):
        """Test clearing specific extension."""
        from omni.core.skills.extensions.fixtures import FixtureRegistry

        FixtureRegistry.register("ext1", "func1", lambda: None)
        FixtureRegistry.register("ext2", "func2", lambda: None)

        FixtureRegistry.clear("ext1")

        assert "ext1" not in FixtureRegistry._registry
        assert "ext2" in FixtureRegistry._registry

    def test_fixture_decorator(self):
        """Test the fixture decorator."""
        from omni.core.skills.extensions.fixtures import fixture

        @fixture("rust_bridge", "git_status")
        def git_status():
            return "Python impl"

        assert git_status._fixture_info == ("rust_bridge", "git_status")

    def test_fixture_manager_discover(self):
        """Test FixtureManager discovers extensions."""
        from omni.core.skills.extensions.fixtures import FixtureManager, FixtureRegistry

        FixtureRegistry.clear()

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_path = Path(tmpdir)
            ext_path = skill_path / "extensions"
            ext_path.mkdir()

            # Create rust_bridge directory first
            rust_bridge_dir = ext_path / "rust_bridge"
            rust_bridge_dir.mkdir()

            # Create extension with FIXTURES
            (rust_bridge_dir / "__init__.py").write_text("""
FIXTURES = {
    "fast_status": lambda: "Rust impl",
}
""")

            manager = FixtureManager(skill_path)
            fixtures = manager.discover_and_register()

            assert "rust_bridge" in fixtures
            assert "fast_status" in fixtures["rust_bridge"]

    def test_fixture_manager_apply_to_module(self):
        """Test applying fixtures to a module with decorated functions."""
        from omni.core.skills.extensions.fixtures import FixtureManager, FixtureRegistry, fixture

        FixtureRegistry.clear()

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_path = Path(tmpdir)
            ext_path = skill_path / "extensions"
            ext_path.mkdir()

            # Create rust_bridge directory first
            rust_bridge_dir = ext_path / "rust_bridge"
            rust_bridge_dir.mkdir()

            # Create extension with FIXTURES
            (rust_bridge_dir / "__init__.py").write_text("""
FIXTURES = {
    "fast_op": lambda: "Rust result",
}
""")

            # Create a real module with decorated function
            import types

            # Create a real module
            test_module = types.ModuleType("scripts.test")

            # Define a function with fixture decorator
            @fixture("rust_bridge", "fast_op")
            def fast_op():
                return "Python result"

            test_module.fast_op = fast_op

            # Verify the fixture info is set
            assert hasattr(test_module.fast_op, "_fixture_info")
            assert test_module.fast_op._fixture_info == ("rust_bridge", "fast_op")

            # Apply fixtures
            manager = FixtureManager(skill_path)
            manager.apply_fixtures_to_module(test_module)

            # Function should be replaced with the fixture implementation
            assert test_module.fast_op() == "Rust result"


class TestExtensionSummary:
    """Test extension summary logging."""

    def test_log_extension_summary_empty(self):
        """Test logging when no extensions loaded."""
        from omni.core.skills.extensions.loader import (
            log_extension_summary,
            reset_extension_stats,
        )

        reset_extension_stats()

        # Should not raise, just log "No extensions loaded"
        log_extension_summary()

    def test_reset_extension_stats(self):
        """Test resetting extension statistics."""
        from omni.core.skills.extensions.loader import (
            _get_stats,
            reset_extension_stats,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ext_dir = Path(tmpdir) / "extensions"
            ext_dir.mkdir()
            (ext_dir / "test.py").write_text("")

            # Simulate loading
            from omni.core.skills.extensions import loader as ext_loader

            ext_loader._extension_stats["test_skill"] = ["test"]

            stats = _get_stats()
            assert "test_skill" in stats

            # Reset
            reset_extension_stats()

            stats = _get_stats()
            assert len(stats) == 0


class TestGetExtensionLoader:
    """Test the get_extension_loader factory function."""

    def test_factory_creates_and_loads(self):
        """Test factory creates loader and loads extensions."""
        from omni.core.skills.extensions import get_extension_loader

        with tempfile.TemporaryDirectory() as tmpdir:
            ext_dir = Path(tmpdir) / "extensions"
            ext_dir.mkdir()
            (ext_dir / "factory.py").write_text("EXT = True")

            loader = get_extension_loader(ext_dir, "factory_skill")

            assert loader is not None
            assert loader.skill_name == "factory_skill"
            assert loader.is_loaded is True


class TestDirectoryLoader:
    """Test directory-based extension loading."""

    def test_directory_loader_class_exists(self):
        """Test DirectoryExtensionLoader class can be imported."""
        from omni.core.skills.extensions.directory_loader import DirectoryExtensionLoader

        assert DirectoryExtensionLoader is not None
        assert callable(DirectoryExtensionLoader)

    def test_directory_loader_has_load_method(self):
        """Test DirectoryExtensionLoader has load method."""
        from omni.core.skills.extensions.directory_loader import DirectoryExtensionLoader

        loader = DirectoryExtensionLoader()
        assert hasattr(loader, "load")
        assert callable(loader.load)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
