"""API surface tests for skills path utilities."""

from __future__ import annotations

import pytest

from omni.foundation.config.skills import SKILLS_DIR


def test_skills_dir_is_explicit_call_api() -> None:
    """SKILLS_DIR should be used as callable, not dynamic attributes."""
    path = SKILLS_DIR(skill="git")
    assert path.name == "git"


def test_skills_dir_rejects_dynamic_attribute_access() -> None:
    """Dynamic attribute access is intentionally unsupported."""
    with pytest.raises(AttributeError):
        _ = SKILLS_DIR.git  # type: ignore[attr-defined]
