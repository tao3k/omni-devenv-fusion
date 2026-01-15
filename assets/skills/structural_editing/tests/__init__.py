"""Tests for structural_edging skill."""

from pathlib import Path

# Get test data directory relative to this file
_TEST_DATA_DIR = Path(__file__).parent / "test_data"


def get_test_file(name: str) -> Path:
    """Get path to test file."""
    return _TEST_DATA_DIR / name
