"""Parameter Validation Module for ODF Skills

Provides fast-fail parameter validation using skill metadata from Rust Scanner.
This enables parameter validation BEFORE expensive kernel initialization.

Usage:
    from omni.core.skills.validation import validate_tool_args

    # Validate before calling kernel
    errors = validate_tool_args("knowledge.ingest_document", {"file_path": "..."})
    if errors:
        handle_errors(errors)
"""

from __future__ import annotations

import json
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.validation")

# Cache for skill tool schemas (loaded from Rust scanner)
_skill_tools_cache: dict[str, dict[str, Any]] = {}


def _load_skills_from_scanner() -> dict[str, dict[str, Any]]:
    """Load all skill tool metadata from the Rust scanner.

    Returns:
        Dict mapping "skill.command" -> tool metadata including input_schema
    """
    try:
        from omni.foundation.config.skills import SKILLS_DIR
        from omni.foundation.bridge import RustVectorStore

        skills_dir = str(SKILLS_DIR())
        store = RustVectorStore()
        skills_data = store.get_skill_index_sync(skills_dir)

        tools: dict[str, dict[str, Any]] = {}
        for skill in skills_data:
            skill_name = skill.get("name", "")
            skill_tools = skill.get("tools", [])

            for tool in skill_tools:
                tool_name = tool.get("name", "")
                if tool_name:
                    full_name = (
                        tool_name
                        if tool_name.startswith(f"{skill_name}.")
                        else f"{skill_name}.{tool_name}"
                    )
                    tools[full_name] = {
                        "name": full_name,
                        "description": tool.get("description", ""),
                        "input_schema": tool.get("input_schema", {}),
                        "required": tool.get("required", []),
                    }

                    # Parse input_schema if it's a JSON string
                    schema = tools[full_name]["input_schema"]
                    if isinstance(schema, str):
                        try:
                            tools[full_name]["input_schema"] = json.loads(schema)
                        except json.JSONDecodeError:
                            tools[full_name]["input_schema"] = {}

        logger.debug(f"Loaded {len(tools)} tools from scanner")
        return tools

    except Exception as e:
        logger.debug(f"Failed to load skills from scanner: {e}")
        return {}


def _get_tools() -> dict[str, dict[str, Any]]:
    """Get cached tools or load from scanner."""
    global _skill_tools_cache

    if not _skill_tools_cache:
        _skill_tools_cache = _load_skills_from_scanner()

    return _skill_tools_cache


def _get_tool(tool_name: str) -> dict[str, Any] | None:
    """Get a specific tool's metadata.

    Handles both naming conventions:
    - knowledge.ingest_document (short form)
    - knowledge.knowledge.ingest_document (full form)
    """
    tools = _get_tools()

    # Try exact match first
    if tool_name in tools:
        return tools[tool_name]

    # Try with doubled skill prefix (e.g., knowledge.ingest_document -> knowledge.knowledge.ingest_document)
    if "." in tool_name:
        parts = tool_name.split(".", 1)
        doubled = f"{parts[0]}.{tool_name}"
        if doubled in tools:
            return tools[doubled]

    return None


def validate_tool_args(tool_name: str, args: dict[str, Any]) -> list[ValidationError]:
    """Validate tool arguments against the tool's input schema.

    This function enables fast-fail validation without kernel initialization.

    Args:
        tool_name: Full tool name (e.g., "knowledge.ingest_document")
        args: Provided arguments dictionary

    Returns:
        List of ValidationError objects (empty if valid)
    """
    errors: list[ValidationError] = []

    # Get tool metadata
    tool = _get_tool(tool_name)
    if not tool:
        logger.debug(f"Tool '{tool_name}' not found in scanner cache")
        return errors

    # Get input schema
    schema = tool.get("input_schema", {})
    if not schema:
        logger.debug(f"Tool '{tool_name}' has no input_schema")
        return errors

    properties = schema.get("properties", {})
    required_fields = schema.get("required", [])

    # Check for missing required fields
    for field in required_fields:
        if field not in args:
            field_info = properties.get(field, {})
            field_type = field_info.get("type", "any")
            description = field_info.get("description", "")

            errors.append(
                ValidationError(
                    field=field,
                    error_type=ErrorType.MISSING_REQUIRED,
                    message=f"Missing required field: '{field}'",
                    suggestion=_get_field_suggestion(field, field_type, description, args),
                )
            )

    return errors


def _get_field_suggestion(
    field: str, field_type: str, description: str, args: dict[str, Any]
) -> str:
    """Generate a helpful suggestion for a missing field."""
    from difflib import SequenceMatcher

    # Check for common typos
    provided_fields = list(args.keys())
    threshold = 0.6

    for candidate in provided_fields:
        ratio = SequenceMatcher(None, field, candidate).ratio()
        if ratio >= threshold:
            return f"Did you mean '{candidate}'?"

    # Provide type-specific examples
    type_examples = {
        "string": f'{{"{field}": "value"}}',
        "integer": f'{{"{field}": 123}}',
        "boolean": f'{{"{field}": true}}',
        "array": f'{{"{field}": ["a", "b", "c"]}}',
    }

    example = type_examples.get(field_type, f'{{"{field}": ...}}')

    # Try to extract example from description
    if "e.g." in description.lower():
        import re

        match = re.search(r'e\.g\.\s*["\']?([^"\'`\n]+)', description, re.IGNORECASE)
        if match:
            example = match.group(1).strip()

    return f'Usage: @omni("skill.command", {example})'


class ErrorType:
    """Error types for parameter validation."""

    MISSING_REQUIRED = "missing_required"
    TYPE_MISMATCH = "type_mismatch"
    INVALID_FORMAT = "invalid_format"
    VALIDATION_FAILED = "validation_failed"


class ValidationError:
    """Represents a single parameter validation error."""

    def __init__(self, field: str, error_type: str, message: str, suggestion: str = ""):
        self.field = field
        self.error_type = error_type
        self.message = message
        self.suggestion = suggestion

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "field": self.field,
            "type": self.error_type,
            "message": self.message,
            "suggestion": self.suggestion,
        }

    def format_for_user(self) -> str:
        """Format error message for user display."""
        parts = [f"❌ {self.message}"]
        if self.suggestion:
            parts.append(f"💡 {self.suggestion}")
        return "\n".join(parts)

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"ValidationError({self.field}, {self.error_type}, {self.message})"


def format_validation_errors(tool_name: str, errors: list[ValidationError]) -> str:
    """Format all validation errors for user-friendly display."""
    if not errors:
        return ""

    header = f"Argument validation failed for '{tool_name}':\n"
    error_lines = [header]

    for error in errors:
        error_lines.append(error.format_for_user())

    return "\n".join(error_lines)


__all__ = [
    "validate_tool_args",
    "ValidationError",
    "ErrorType",
    "format_validation_errors",
]
