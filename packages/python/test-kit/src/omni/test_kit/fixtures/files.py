"""File-system fixtures for temporary test artifacts."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def temp_yaml_file(tmp_path: Path) -> Callable[[str, str], Path]:
    """Create temporary YAML file content and return its path.

    Usage:
        path = temp_yaml_file("invalid.yaml", "pipeline: bad")
    """

    def _create(filename: str, content: str) -> Path:
        target = tmp_path / filename
        target.write_text(content, encoding="utf-8")
        return target

    return _create


__all__ = ["temp_yaml_file"]
