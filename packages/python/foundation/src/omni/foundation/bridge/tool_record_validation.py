"""Tool Record Validation - Strict contract for Rust → Python data flow.

Rust is the single source of truth; Python receives and validates.
No inference in Python - invalid data fails fast with clear errors.

Two contracts:
1. list_all_tools (validate_tool_record): id, skill_name, tool_name
2. PySkillScanner scanned records (validate_scanned_tool_record): schema, tool_name, skill_name, etc.
"""

from __future__ import annotations

import re

# Schema version for PySkillScanner command-index records
COMMAND_INDEX_SCHEMA_V1 = "v1"

# Required and allowed keys for scanned tool records (tools_loader_index, PySkillScanner)
_SCANNED_REQUIRED_KEYS = frozenset(
    {
        "schema",
        "tool_name",
        "skill_name",
        "file_path",
        "function_name",
        "execution_mode",
        "keywords",
        "input_schema",
        "docstring",
        "file_hash",
        "category",
    }
)
_SCANNED_ALLOWED_KEYS = _SCANNED_REQUIRED_KEYS | frozenset({"description"})


class ToolRecordValidationError(ValueError):
    """Raised when a tool record fails validation (Rust contract broken)."""

    def __init__(self, message: str, record: dict | None = None, index: int | None = None):
        super().__init__(message)
        self.record = record
        self.index = index


# Required keys - must be non-null and non-empty
_REQUIRED_KEYS = frozenset({"id", "skill_name", "tool_name"})
_SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_CANONICAL_TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$")


def validate_tool_record(record: dict, *, index: int | None = None) -> None:
    """Validate a single tool record. Raises ToolRecordValidationError if invalid.

    Args:
        record: Flattened tool dict from Rust list_all_tools.
        index: Optional 0-based index for error context.

    Raises:
        ToolRecordValidationError: When required fields are missing or empty.
    """
    if not isinstance(record, dict):
        raise ToolRecordValidationError(
            f"Tool record must be dict, got {type(record).__name__}",
            record=record,
            index=index,
        )
    missing = _REQUIRED_KEYS - set(record.keys())
    if missing:
        raise ToolRecordValidationError(
            f"Missing required keys: {sorted(missing)}. "
            f"Rust list_all_tools must populate skill_name, tool_name.",
            record=record,
            index=index,
        )
    for key in _REQUIRED_KEYS:
        val = record.get(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            raise ToolRecordValidationError(
                f"Required key '{key}' must be non-null and non-empty. "
                f"Rust contract guarantees this via infer_skill_tool_from_id.",
                record=record,
                index=index,
            )

    skill_name = str(record.get("skill_name", "")).strip()
    tool_name = str(record.get("tool_name", "")).strip()
    if not _SKILL_NAME_PATTERN.fullmatch(skill_name):
        raise ToolRecordValidationError(
            f"Invalid skill_name format: '{skill_name}'. Expected /^[A-Za-z][A-Za-z0-9_]*$/",
            record=record,
            index=index,
        )
    if not _CANONICAL_TOOL_NAME_PATTERN.fullmatch(tool_name):
        raise ToolRecordValidationError(
            f"Invalid tool_name format: '{tool_name}'. "
            "Expected canonical form 'skill.command' with alnum/underscore segments.",
            record=record,
            index=index,
        )
    if not tool_name.startswith(f"{skill_name}."):
        raise ToolRecordValidationError(
            f"tool_name '{tool_name}' must be prefixed by skill_name '{skill_name}'.",
            record=record,
            index=index,
        )


def validate_tool_records(records: list[dict]) -> None:
    """Validate a list of tool records. Fails on first invalid record.

    Args:
        records: List of flattened tool dicts from Rust list_all_tools.

    Raises:
        ToolRecordValidationError: When any record is invalid.
    """
    for i, rec in enumerate(records):
        validate_tool_record(rec, index=i)


def validate_scanned_tool_record(record: dict, *, index: int | None = None) -> None:
    """Validate a PySkillScanner scanned tool record. Strict schema, no extra keys.

    Args:
        record: Scanned tool dict from PySkillScanner.scan_skill_with_tools.
        index: Optional 0-based index for error context.

    Raises:
        ToolRecordValidationError: When schema validation fails.
    """
    if not isinstance(record, dict):
        raise ToolRecordValidationError(
            "schema validation failed: record must be dict",
            record=record,
            index=index,
        )
    extra = set(record.keys()) - _SCANNED_ALLOWED_KEYS
    if extra:
        raise ToolRecordValidationError(
            f"Additional properties are not allowed: {sorted(extra)}",
            record=record,
            index=index,
        )
    missing = _SCANNED_REQUIRED_KEYS - set(record.keys())
    if missing:
        raise ToolRecordValidationError(
            f"schema validation failed: missing required keys {sorted(missing)}",
            record=record,
            index=index,
        )
    for key in _SCANNED_REQUIRED_KEYS:
        val = record.get(key)
        if val is None:
            raise ToolRecordValidationError(
                f"schema validation failed: required key '{key}' must be present",
                record=record,
                index=index,
            )
        if key != "docstring" and isinstance(val, str) and not val.strip():
            raise ToolRecordValidationError(
                f"schema validation failed: required key '{key}' must be non-empty",
                record=record,
                index=index,
            )
