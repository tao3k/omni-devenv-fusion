"""Schema validation tests for Rust scanner command-index records."""

from __future__ import annotations

import pytest

from omni.foundation.bridge.tool_record_validation import (
    COMMAND_INDEX_SCHEMA_V1,
    ToolRecordValidationError,
    validate_scanned_tool_record,
)


def _valid_scan_record() -> dict:
    return {
        "schema": COMMAND_INDEX_SCHEMA_V1,
        "tool_name": "knowledge.recall",
        "description": "Recall",
        "skill_name": "knowledge",
        "file_path": "assets/skills/knowledge/scripts/recall.py",
        "function_name": "recall",
        "execution_mode": "sync",
        "keywords": [],
        "input_schema": "{}",
        "docstring": "",
        "file_hash": "deadbeef",
        "category": "search",
    }


def test_validate_scanned_tool_record_accepts_valid_payload() -> None:
    validate_scanned_tool_record(_valid_scan_record())


def test_validate_scanned_tool_record_rejects_missing_required_field() -> None:
    bad = _valid_scan_record()
    bad.pop("tool_name")
    with pytest.raises(ToolRecordValidationError, match="schema validation failed"):
        validate_scanned_tool_record(bad)


def test_validate_scanned_tool_record_rejects_extra_field() -> None:
    bad = _valid_scan_record()
    bad["unexpected"] = "boom"
    with pytest.raises(ToolRecordValidationError, match="Additional properties are not allowed"):
        validate_scanned_tool_record(bad)
