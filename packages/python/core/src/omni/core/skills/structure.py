"""
structure.py - Skill Structure Validation Logic

Provides utilities for validating and generating structure tests for skills.
Based on ODF-EP v7.0 skill architecture.
"""

from __future__ import annotations

from typing import Any, Callable


def get_skill_structure() -> dict[str, list[str] | dict[str, Any]]:
    """
    Load ODF-EP v7.0 skill structure from settings.yaml.

    Returns:
        dict with 'required', 'default', 'disallowed' keys
    """
    from omni.foundation.config import get_setting

    structure = get_setting("skills.architecture.structure", {})
    return {
        "required": [item.get("path", "") for item in structure.get("required", [])],
        "default": [item.get("path", "") for item in structure.get("default", [])],
        "disallowed": structure.get("disallowed_files", []),
    }


def validate_structure(skill_name: str | None = None):
    """
    [Macro] Auto-generate structure validation tests for a skill.

    Reads from assets/settings.yaml (skills.architecture.structure) and
    generates pytest tests that verify:
    - All required files/dirs exist
    - No disallowed files exist
    - Default structure is correct

    Usage in conftest.py or test file:
        from omni.core.skills.structure import validate_structure

        # Auto-generate tests for git skill
        validate_structure("git")

    This creates tests:
        test_skill_has_required_files
        test_skill_has_tests_directory
        test_skill_has_no_disallowed_files

    Args:
        skill_name: Skill name (auto-detected from module if not provided)
    """

    def decorator(func: Callable) -> Callable:
        # Get skill name from module
        import sys

        module = sys.modules.get(func.__module__)
        target_skill = skill_name
        if target_skill is None and module:
            parts = module.__name__.split(".")
            if len(parts) >= 2:
                target_skill = parts[-2] if parts[-1] == "tools" else parts[-1]

        # Attach metadata for test generation
        func._validate_skill = target_skill
        return func

    return decorator


def generate_structure_tests(skill_name: str) -> dict[str, Callable]:
    """
    Generate structure validation test functions for a skill.

    This is called by conftest.py to register tests dynamically.

    Args:
        skill_name: Name of the skill to validate

    Returns:
        dict of test_name -> test_function
    """
    from omni.foundation.config.skills import SKILLS_DIR

    structure = get_skill_structure()
    skill_path = SKILLS_DIR(skill=skill_name)

    tests = {}

    # Test: Required files exist
    def make_test_required():
        def test():
            for item in structure.get("required", []):
                path = skill_path / item
                assert path.exists(), f"Required {item} must exist"

        return test

    tests["test_skill_has_required_files"] = make_test_required()

    # Test: Disallowed files don't exist
    def make_test_disallowed():
        def test():
            for item in structure.get("disallowed", []):
                path = skill_path / item
                assert not path.exists(), f"Disallowed {item} must NOT exist"

        return test

    tests["test_skill_has_no_disallowed_files"] = make_test_disallowed()

    # Test: Default directories optional (just check they exist if present)
    def make_test_defaults():
        def test():
            for item in structure.get("default", []):
                path = skill_path / item
                if path.exists():
                    assert path.is_dir(), f"{item} should be a directory"

        return test

    tests["test_skill_default_structure"] = make_test_defaults()

    return tests


__all__ = [
    "get_skill_structure",
    "validate_structure",
    "generate_structure_tests",
]
