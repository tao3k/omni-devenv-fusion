"""Tests for broken math library."""

import pytest
from scripts.broken_math import add, multiply, factorial, is_even


def test_add():
    """Test addition."""
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0


def test_multiply():
    """Test multiplication."""
    assert multiply(3, 4) == 12
    assert multiply(0, 5) == 0
    assert multiply(5, 0) == 0


def test_factorial():
    """Test factorial."""
    assert factorial(0) == 1
    assert factorial(1) == 1
    assert factorial(5) == 120
    assert factorial(7) == 5040


def test_is_even():
    """Test even detection."""
    assert is_even(2) == True
    assert is_even(4) == True
    assert is_even(3) == False
    assert is_even(0) == True
