"""
Unit tests for omni.foundation.utils.formatting
"""

import pytest
from omni.foundation.utils.formatting import one_line_preview, sanitize_tool_args


def test_one_line_preview_none():
    assert one_line_preview(None) == "None"


def test_one_line_preview_short_string():
    text = "Hello World"
    assert one_line_preview(text) == "Hello World"


def test_one_line_preview_with_newlines():
    text = "Line 1\nLine 2\r\nLine 3"
    # Newlines should be replaced by spaces and multiple spaces compressed
    assert one_line_preview(text) == "Line 1 Line 2 Line 3"


def test_one_line_preview_truncation():
    text = "A" * 100
    preview = one_line_preview(text, max_len=10)
    assert preview == "AAAAAAAAAA... (+90 chars)"


def test_sanitize_tool_args_empty():
    assert sanitize_tool_args({}) == ""


def test_sanitize_tool_args_normal():
    args = {"path": "src/main.py", "mode": "r"}
    result = sanitize_tool_args(args)
    assert "path=src/main.py" in result
    assert "mode=r" in result


def test_sanitize_tool_args_large_field():
    args = {"path": "test.txt", "content": "This is a very long content\n" * 10}
    result = sanitize_tool_args(args)
    assert "path=test.txt" in result
    assert 'content="' in result
    assert "(+" in result  # Should be truncated


def test_sanitize_tool_args_complex_types():
    args = {"data": [1, 2, 3], "metadata": {"key": "value"}}
    result = sanitize_tool_args(args)
    # Since 'data' is in LARGE_FIELDS, it gets quotes
    assert 'data="[1, 2, 3]"' in result
    assert "metadata={'key': 'value'}" in result
