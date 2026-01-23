"""
schemas.py - Tool Schema Extraction

Extracts tool schemas from skill handler signatures using inspect.
Ensures LLM receives correct parameter names (prevents guessing bugs).

CRITICAL: This prevents the bug where LLM guesses 'path' instead of 'file_path'.
"""

import inspect
from typing import Any, Dict, List, Optional


# Parameters that are injected by the framework (skip these)
SKIPPED_PARAMS = frozenset({"cwd", "skills_dir", "paths"})


def extract_tool_schemas(commands: List[str], get_command) -> List[Dict[str, Any]]:
    """Extract tool schemas from skill command handlers.

    Args:
        commands: List of command names (e.g., "filesystem.read_file")
        get_command: Function to get handler for a command name

    Returns:
        List of tool schemas in Anthropic format
    """
    tools = []

    for cmd in commands:
        parts = cmd.split(".", 1)
        if len(parts) != 2:
            continue

        skill_name, command_name = parts

        handler = get_command(cmd)
        if handler is None:
            continue

        schema = _extract_schema_from_handler(handler, skill_name, command_name)
        if schema:
            tools.append(schema)

    return tools


def _extract_schema_from_handler(
    handler, skill_name: str, command_name: str
) -> Optional[Dict[str, Any]]:
    """Extract a single tool schema from a handler function.

    Uses _skill_config first (Foundation V2), then falls back to inspect.signature.
    """
    try:
        # Check for _skill_config first (Foundation V2 decorator with autowire)
        config = getattr(handler, "_skill_config", None)
        if config:
            raw_schema = config.get("input_schema", {})
            if raw_schema:
                return {
                    "name": f"{skill_name}.{command_name}",
                    "description": config.get(
                        "description", f"Execute {command_name} command in {skill_name} skill"
                    ),
                    "input_schema": raw_schema,
                }

        # Fallback: inspect signature for legacy handlers
        sig = inspect.signature(handler)
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            # Skip framework-injected parameters
            if param_name in SKIPPED_PARAMS:
                continue

            # Determine JSON schema type
            param_type = _get_param_type(param)

            # Build description
            description = param_name
            if param.default is not inspect.Parameter.empty:
                description += f" (default: {param.default})"

            properties[param_name] = {
                "type": param_type,
                "description": description,
            }

            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        return {
            "name": f"{skill_name}.{command_name}",
            "description": f"Execute {command_name} command in {skill_name} skill",
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    except Exception:
        # Fallback: minimal schema if signature inspection fails
        return {
            "name": f"{skill_name}.{command_name}",
            "description": f"Execute {command_name} command in {skill_name} skill",
            "input_schema": {
                "type": "object",
                "properties": {
                    "_skip_logging": {
                        "type": "boolean",
                        "description": "Skip logging this call (for sensitive data)",
                    }
                },
                "required": [],
            },
        }


def _get_param_type(param) -> str:
    """Get JSON schema type from parameter annotation."""
    if param.annotation is str:
        return "string"
    elif param.annotation is int:
        return "integer"
    elif param.annotation is bool:
        return "boolean"
    elif hasattr(param.annotation, "__origin__"):
        # Handle Optional, List, etc.
        origin = str(param.annotation)
        if "str" in origin:
            return "string"
        elif "int" in origin:
            return "integer"
        elif "bool" in origin:
            return "boolean"
        elif "list" in origin:
            return "array"
    return "string"  # Default
