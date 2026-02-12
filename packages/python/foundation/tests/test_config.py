"""
Config Directory Tests

Tests for omni.foundation.config.directory module.
"""


class TestConfDirFunctions:
    """Test configuration directory functions."""

    def test_set_conf_dir(self):
        """Test set_conf_dir() function."""
        import os

        from omni.foundation.config.directory import get_conf_dir, set_conf_dir

        original = os.environ.get("PRJ_CONFIG_HOME")
        try:
            set_conf_dir("/custom/path")
            assert get_conf_dir() == "/custom/path/omni-dev-fusion"
        finally:
            if original is None:
                os.environ.pop("PRJ_CONFIG_HOME", None)
            else:
                os.environ["PRJ_CONFIG_HOME"] = original
            from omni.foundation.config.dirs import PRJ_DIRS

            PRJ_DIRS.clear_cache()

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
