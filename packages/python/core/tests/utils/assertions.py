"""
Custom Assertion Helpers for Tests.

This module provides reusable assertion functions to reduce boilerplate
in test files.

Usage:
    from tests.utils.assertions import assert_contains, assert_is_subclass
"""

from typing import Any


def assert_contains(haystack: str, needle: str, msg: str = "") -> None:
    """Assert that a string contains a substring."""
    assert needle in haystack, f"{msg} Expected '{needle}' in '{haystack[:100]}...'"


def assert_not_contains(haystack: str, needle: str, msg: str = "") -> None:
    """Assert that a string does not contain a substring."""
    assert needle not in haystack, f"{msg} Unexpected '{needle}' in '{haystack[:100]}...'"


def assert_type(obj: Any, expected_type: type, msg: str = "") -> None:
    """Assert that an object is of expected type."""
    assert isinstance(obj, expected_type), (
        f"{msg} Expected {expected_type.__name__}, got {type(obj).__name__}"
    )


def assert_is_subclass(cls: type, base_class: type, msg: str = "") -> None:
    """Assert that a class is a subclass of expected base."""
    assert issubclass(cls, base_class), (
        f"{msg} {cls.__name__} should be subclass of {base_class.__name__}"
    )


def assert_has_attr(obj: Any, attr: str, msg: str = "") -> None:
    """Assert that an object has expected attribute."""
    assert hasattr(obj, attr), f"{msg} Object {type(obj).__name__} missing attribute '{attr}'"


def assert_len(obj: Any, length: int, msg: str = "") -> None:
    """Assert that an object has expected length."""
    assert len(obj) == length, f"{msg} Expected length {length}, got {len(obj)}"


def assert_empty(obj: Any, msg: str = "") -> None:
    """Assert that an object is empty."""
    assert len(obj) == 0, f"{msg} Expected empty, got {len(obj)} items"


def assert_not_empty(obj: Any, msg: str = "") -> None:
    """Assert that an object is not empty."""
    assert len(obj) > 0, f"{msg} Expected non-empty collection"


def assert_equal(actual: Any, expected: Any, msg: str = "") -> None:
    """Assert equality with custom message."""
    assert actual == expected, f"{msg} Expected {expected!r}, got {actual!r}"


def assert_is_none(obj: Any, msg: str = "") -> None:
    """Assert that an object is None."""
    assert obj is None, f"{msg} Expected None, got {obj!r}"


def assert_is_not_none(obj: Any, msg: str = "") -> None:
    """Assert that an object is not None."""
    assert obj is not None, f"{msg} Expected non-None value"


def assert_raises(
    exception_type: type[Exception], func: callable, msg: str = ""
) -> Exception | None:
    """Assert that a function raises expected exception."""
    try:
        func()
        raise AssertionError(f"{msg} Expected {exception_type.__name__} to be raised")
    except exception_type:
        pass  # Expected
    return None
