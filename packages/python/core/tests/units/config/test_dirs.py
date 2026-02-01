"""Tests for omni.foundation.config.dirs module."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestGetMemoryDbPath:
    """Tests for get_memory_db_path function."""

    def test_returns_lance_file_in_vector_dir(self):
        """Test that memory DB path is in the vector DB directory."""
        from omni.foundation.config.dirs import get_memory_db_path, get_vector_db_path

        memory_path = get_memory_db_path()
        vector_path = get_vector_db_path()

        assert memory_path == vector_path / "memory.lance"
        assert memory_path.suffix == ".lance"

    def test_returns_absolute_path(self):
        """Test that the returned path is absolute."""
        from omni.foundation.config.dirs import get_memory_db_path

        memory_path = get_memory_db_path()

        assert memory_path.is_absolute()

    def test_memory_db_path_not_in_root(self):
        """Test that memory DB is not in project root directly."""
        from omni.foundation.config.dirs import get_memory_db_path

        memory_path = get_memory_db_path()

        # Should be in .cache/omni-vector/, not in project root
        assert ".cache" in str(memory_path)
        assert "omni-vector" in str(memory_path)
