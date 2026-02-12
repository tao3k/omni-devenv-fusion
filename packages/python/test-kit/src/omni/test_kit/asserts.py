"""Assertion helpers for common test patterns.

Provides a collection of assertion functions that provide clear error messages
and work seamlessly with pytest.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

# Type alias for assertion functions
AssertionFunc = Callable[..., None]


def assert_equal(expected: Any, actual: Any, msg: str = "") -> None:
    """Assert that expected equals actual."""
    if expected != actual:
        pytest.fail(
            f"{msg}\nExpected: {expected!r}\nActual:   {actual!r}"
            if msg
            else f"Expected {expected!r}, got {actual!r}"
        )


def assert_not_equal(expected: Any, actual: Any, msg: str = "") -> None:
    """Assert that expected does NOT equal actual."""
    if expected == actual:
        pytest.fail(
            f"{msg}\nValues should be different: {expected!r}"
            if msg
            else "Values should be different"
        )


def assert_true(value: Any, msg: str = "") -> None:
    """Assert that value is truthy."""
    if not value:
        pytest.fail(msg or f"Expected truthy value, got {value!r}")


def assert_false(value: Any, msg: str = "") -> None:
    """Assert that value is falsy."""
    if value:
        pytest.fail(msg or f"Expected falsy value, got {value!r}")


def assert_is_none(value: Any, msg: str = "") -> None:
    """Assert that value is None."""
    if value is not None:
        pytest.fail(msg or f"Expected None, got {value!r}")


def assert_is_not_none(value: Any, msg: str = "") -> None:
    """Assert that value is not None."""
    if value is None:
        pytest.fail(msg or "Expected non-None value")


def assert_in(item: Any, container: Any, msg: str = "") -> None:
    """Assert that item is in container."""
    if item not in container:
        pytest.fail(
            f"{msg}\nItem {item!r} not found in {container!r}"
            if msg
            else f"Item {item!r} not in {container!r}"
        )


def assert_not_in(item: Any, container: Any, msg: str = "") -> None:
    """Assert that item is NOT in container."""
    if item in container:
        pytest.fail(
            f"{msg}\nItem {item!r} should not be in {container!r}"
            if msg
            else f"Item {item!r} should not be in {container!r}"
        )


def assert_raises(
    expected_exception: type[Exception], callable: Callable | None = None, *args, **kwargs
) -> Any:
    """Assert that an exception is raised.

    Can be used as a context manager or with a callable.
    """
    if callable is None:
        return pytest.raises(expected_exception)

    with pytest.raises(expected_exception):
        callable(*args, **kwargs)


def assert_length(container: Any, expected_length: int, msg: str = "") -> None:
    """Assert that container has expected length."""
    actual_length = len(container)
    if actual_length != expected_length:
        pytest.fail(
            f"{msg}\nExpected length: {expected_length}\nActual length: {actual_length}"
            if msg
            else f"Expected {expected_length} items, got {actual_length}"
        )


def assert_empty(container: Any, msg: str = "") -> None:
    """Assert that container is empty."""
    if container:
        pytest.fail(msg or f"Expected empty container, got {container!r}")


def assert_not_empty(container: Any, msg: str = "") -> None:
    """Assert that container is NOT empty."""
    if not container:
        pytest.fail(msg or "Expected non-empty container")


def assert_starts_with(prefix: str, string: str, msg: str = "") -> None:
    """Assert that string starts with prefix."""
    if not string.startswith(prefix):
        pytest.fail(
            f"{msg}\nString should start with {prefix!r}\nString: {string!r}"
            if msg
            else f"String {string!r} does not start with {prefix!r}"
        )


def assert_ends_with(suffix: str, string: str, msg: str = "") -> None:
    """Assert that string ends with suffix."""
    if not string.endswith(suffix):
        pytest.fail(
            f"{msg}\nString should end with {suffix!r}\nString: {string!r}"
            if msg
            else f"String {string!r} does not end with {suffix!r}"
        )


def assert_contains(substring: str, string: str, msg: str = "") -> None:
    """Assert that string contains substring."""
    if substring not in string:
        pytest.fail(
            f"{msg}\nString should contain {substring!r}\nString: {string!r}"
            if msg
            else f"String {string!r} does not contain {substring!r}"
        )


def assert_match(pattern: str, string: str, msg: str = "") -> None:
    """Assert that string matches regex pattern."""
    import re

    if not re.search(pattern, string):
        pytest.fail(
            f"{msg}\nString should match pattern {pattern!r}\nString: {string!r}"
            if msg
            else f"String {string!r} does not match pattern {pattern!r}"
        )


# =============================================================================
# ToolResponse Assertions (for MCP tool testing)
# =============================================================================


def assert_response_ok(response: Any, msg: str = "") -> None:
    """Assert that a tool response indicates success."""
    from omni.core.responses import ResponseStatus

    if hasattr(response, "status"):
        status = response.status
        if status != ResponseStatus.SUCCESS:
            pytest.fail(
                f"{msg}\nExpected SUCCESS response, got {status.value}\nError: {response.error}"
                if hasattr(response, "error")
                else f"Expected SUCCESS, got {status.value}"
            )
    else:
        pytest.fail(
            f"{msg}\nResponse is not a ToolResponse object: {response!r}"
            if msg
            else "Response is not a ToolResponse object"
        )


def assert_response_error(response: Any, msg: str = "") -> None:
    """Assert that a tool response indicates an error."""
    from omni.core.responses import ResponseStatus

    if hasattr(response, "status"):
        status = response.status
        if status != ResponseStatus.ERROR:
            pytest.fail(
                f"{msg}\nExpected ERROR response, got {status.value}"
                if msg
                else f"Expected ERROR, got {status.value}"
            )
    else:
        pytest.fail(
            f"{msg}\nResponse is not a ToolResponse object: {response!r}"
            if msg
            else "Response is not a ToolResponse object"
        )


def assert_response_blocked(response: Any, msg: str = "") -> None:
    """Assert that a tool response indicates blocked (permission denied)."""
    from omni.core.responses import ResponseStatus

    if hasattr(response, "status"):
        status = response.status
        if status != ResponseStatus.BLOCKED:
            pytest.fail(
                f"{msg}\nExpected BLOCKED response, got {status.value}"
                if msg
                else f"Expected BLOCKED, got {status.value}"
            )
    else:
        pytest.fail(
            f"{msg}\nResponse is not a ToolResponse object: {response!r}"
            if msg
            else "Response is not a ToolResponse object"
        )


def assert_has_error(response: Any, expected_code: str | None = None, msg: str = "") -> None:
    """Assert that response has an error and optionally check error code."""

    if not hasattr(response, "error"):
        pytest.fail(f"{msg}\nResponse has no error field" if msg else "Response has no error field")

    if not response.error:
        pytest.fail(f"{msg}\nResponse error is empty" if msg else "Response error is empty")

    if (
        expected_code is not None
        and hasattr(response, "error_code")
        and response.error_code != expected_code
    ):
        pytest.fail(
            f"{msg}\nExpected error code {expected_code!r}, got {response.error_code!r}"
            if msg
            else f"Expected error code {expected_code!r}, got {response.error_code!r}"
        )


def assert_response_data(response: Any, expected_data: Any = None, msg: str = "") -> None:
    """Assert that response has expected data."""
    if not hasattr(response, "data"):
        pytest.fail(f"{msg}\nResponse has no data field" if msg else "Response has no data field")

    if expected_data is not None and response.data != expected_data:
        pytest.fail(
            f"{msg}\nExpected data: {expected_data!r}\nActual data: {response.data!r}"
            if msg
            else f"Expected {expected_data!r}, got {response.data!r}"
        )


def assert_response_metadata(
    response: Any, expected_key: str | None = None, expected_value: Any = None, msg: str = ""
) -> None:
    """Assert that response has expected metadata."""
    if not hasattr(response, "metadata"):
        pytest.fail(
            f"{msg}\nResponse has no metadata field" if msg else "Response has no metadata field"
        )

    if expected_key is not None:
        if expected_key not in response.metadata:
            pytest.fail(
                f"{msg}\nMetadata missing key {expected_key!r}\nMetadata: {response.metadata}"
                if msg
                else f"Metadata missing key {expected_key!r}"
            )

        if expected_value is not None and response.metadata.get(expected_key) != expected_value:
            pytest.fail(
                f"{msg}\nMetadata[{expected_key!r}] = {response.metadata.get(expected_value)!r}, expected {expected_value!r}"
                if msg
                else f"Metadata[{expected_key!r}] mismatch"
            )


# =============================================================================
# Skill Test Assertions
# =============================================================================


def assert_skill_loaded(skill_info: Any, expected_name: str | None = None, msg: str = "") -> None:
    """Assert that a skill was loaded correctly."""
    if (
        expected_name is not None
        and hasattr(skill_info, "name")
        and skill_info.name != expected_name
    ):
        pytest.fail(
            f"{msg}\nExpected skill name {expected_name!r}, got {skill_info.name!r}"
            if msg
            else f"Expected skill name {expected_name!r}, got {skill_info.name!r}"
        )


def assert_skill_has_permission(skill_info: Any, permission: str, msg: str = "") -> None:
    """Assert that a skill has the expected permission."""
    if not hasattr(skill_info, "permissions"):
        pytest.fail(
            f"{msg}\nSkill has no permissions field" if msg else "Skill has no permissions field"
        )

    if permission not in skill_info.permissions:
        pytest.fail(
            f"{msg}\nSkill missing permission {permission!r}\nPermissions: {skill_info.permissions}"
            if msg
            else f"Skill missing permission {permission!r}"
        )


def assert_skill_has_command(skill_commands: dict, command_name: str, msg: str = "") -> None:
    """Assert that a skill has the expected command."""
    if command_name not in skill_commands:
        pytest.fail(
            f"{msg}\nSkill missing command {command_name!r}\nCommands: {list(skill_commands.keys())}"
            if msg
            else f"Skill missing command {command_name!r}"
        )


# =============================================================================
# Router Assertions
# =============================================================================


def assert_route_result_shape(result: Any, msg: str = "") -> None:
    """Assert a route result exposes required fields and canonical tool id shape."""
    required_fields = ("skill_name", "command_name", "score", "confidence")
    for field in required_fields:
        if not hasattr(result, field):
            pytest.fail(
                f"{msg}\nMissing route field: {field!r}"
                if msg
                else f"Missing route field: {field!r}"
            )

    skill_name = getattr(result, "skill_name", None)
    command_name = getattr(result, "command_name", None)
    if not skill_name or not command_name:
        pytest.fail(msg or "Route result requires non-empty skill_name and command_name")

    full_id = f"{skill_name}.{command_name}"
    if "." not in full_id:
        pytest.fail(msg or f"Expected canonical tool id with dot, got {full_id!r}")

    score = getattr(result, "score", None)
    if score is None or float(score) <= 0:
        pytest.fail(msg or f"Expected positive route score, got {score!r}")


def assert_tool_family_match(
    tool_names: list[str],
    *,
    substrings: list[str] | None = None,
    exact: list[str] | None = None,
    msg: str = "",
) -> None:
    """Assert at least one tool name matches expected family patterns."""
    substrings = substrings or []
    exact = exact or []

    matched = False
    for name in tool_names:
        if name in exact or any(token in name for token in substrings):
            matched = True
            break

    if not matched:
        expectation = f"substrings={substrings}, exact={exact}"
        pytest.fail(
            f"{msg}\nNo tool matched {expectation}. got={tool_names}"
            if msg
            else f"No tool matched {expectation}. got={tool_names}"
        )


def assert_route_results_list(results: Any, *, allow_empty: bool = True, msg: str = "") -> None:
    """Assert list shape for route results and optionally validate each entry."""
    if not isinstance(results, list):
        pytest.fail(msg or f"Expected list route results, got {type(results).__name__}")
    if not allow_empty and not results:
        pytest.fail(msg or "Expected non-empty route results list")
    for result in results:
        assert_route_result_shape(result, msg=msg)
