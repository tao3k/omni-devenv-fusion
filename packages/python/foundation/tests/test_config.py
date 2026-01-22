"""
Config Directory Tests

Tests for omni.foundation.config.directory module.
"""

import pytest
from pathlib import Path


class TestConfDirFunctions:
    """Test configuration directory functions."""

    def test_set_conf_dir(self):
        """Test set_conf_dir() function."""
        from omni.foundation.config.directory import set_conf_dir, get_conf_dir

        original = get_conf_dir()
        try:
            set_conf_dir("/custom/path")
            assert get_conf_dir() == "/custom/path"
        finally:
            # Reset
            import omni.foundation.config.directory as module

            module._CONF_DIR = None

    def test_get_conf_dir_returns_string(self):
        """Test get_conf_dir() returns a string."""
        from omni.foundation.config.directory import get_conf_dir

        result = get_conf_dir()
        assert isinstance(result, str)
        assert len(result) > 0


class TestConfDirModule:
    """Test configuration directory module."""

    def test_module_exports(self):
        """Test module exports expected functions."""
        from omni.foundation.config import directory

        assert hasattr(directory, "set_conf_dir")
        assert hasattr(directory, "get_conf_dir")
        assert hasattr(directory, "__all__")

    def test_all_contains_exports(self):
        """Test __all__ contains expected items."""
        from omni.foundation.config import directory

        expected = ["set_conf_dir", "get_conf_dir"]
        for item in expected:
            assert item in directory.__all__
