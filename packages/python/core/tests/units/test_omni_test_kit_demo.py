"""Example tests demonstrating the enhanced Omni Test Kit features.

This file shows how to use:
    - Testing layer markers (@unit, @integration, @cloud)
    - Assertion helpers (assert_response_ok, assert_has_error, etc.)
    - Skill test builder utilities
"""

from __future__ import annotations

import pytest

# Import markers and assertions from test-kit
from omni.test_kit.plugin import unit, integration, cloud
from omni.test_kit.asserts import (
    assert_response_ok,
    assert_has_error,
    assert_equal,
    assert_in,
    assert_length,
    assert_true,
)
from omni.test_kit.decorators import omni_skill
from omni.test_kit.fixtures import SkillTestBuilder
from omni.core.responses import ToolResponse


# =============================================================================
# Testing Layer Markers Examples
# =============================================================================


@unit
def test_with_unit_marker() -> None:
    """This is a unit test - fast, isolated."""
    assert_equal(1, 1)
    assert_true(True)


@integration
async def test_with_integration_marker() -> None:
    """This is an integration test - uses real components."""
    # Integration with real scanner would go here
    assert_true(True)


@cloud
async def test_with_cloud_marker() -> None:
    """This is a cloud test - requires external services."""
    pytest.skip("Requires external LanceDB")


# =============================================================================
# Assertion Helpers Examples
# =============================================================================


@unit
def test_assertion_helpers() -> None:
    """Demonstrate assertion helpers."""
    # Basic assertions
    assert_equal(10, 10)
    assert_in("key", {"key": "value"})
    assert_length([1, 2, 3], 3)
    assert_true(True)


@unit
def test_response_assertions() -> None:
    """Demonstrate ToolResponse assertions."""
    # Create a success response
    response = ToolResponse.success(data={"result": "ok"}, metadata={"source": "test"})
    assert_response_ok(response)

    # Create an error response
    error_response = ToolResponse.error(message="Not found", code="3001")
    assert_has_error(error_response, expected_code="3001")


# =============================================================================
# Skill Test Builder Examples
# =============================================================================


@unit
def test_skill_builder() -> None:
    """Demonstrate SkillTestBuilder for creating test skills."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Build a skill
        builder = SkillTestBuilder("my_test_skill")
        builder.with_metadata(
            version="1.0.0",
            description="A test skill",
            routing_keywords=["test", "demo"],
            authors=["Test Author"],
            permissions=["filesystem:read"],
        )
        builder.with_script("example.py", "# Example script")

        # Create the skill
        skill_path = builder.create(tmpdir)

        # Verify creation - path should end with my_test_skill
        assert_true(skill_path.endswith("my_test_skill"))


# =============================================================================
# Custom Markers
# =============================================================================


@omni_skill("git")
def test_git_specific() -> None:
    """Test specific to the git skill."""
    assert_true(True)


# =============================================================================
# Parameterized Tests
# =============================================================================


@unit
@pytest.mark.parametrize(
    "value,expected",
    [
        (1, 1),
        (2, 2),
        (3, 3),
    ],
)
def test_parametrized(value: int, expected: int) -> None:
    """Parametrized test example."""
    assert_equal(value, expected)
