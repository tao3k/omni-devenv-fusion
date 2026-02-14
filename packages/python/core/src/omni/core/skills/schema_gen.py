"""
schema_gen.py - Tool Schema Generator

Generates machine-readable schemas for all registered MCP Tools.
Uses shared schemas from packages/shared/schemas/ for cross-language consistency.

Usage:
    from omni.core.skills.schema_gen import generate_tool_schemas, export_openapi

    # Generate all tool schemas
    schemas = generate_tool_schemas()

    # Export as OpenAPI-compatible format
    openapi = export_openapi()
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omni.core.skills.variants import get_variant_registry

# Import registry from tools_loader (populated by @skill_command decorator)
from omni.core.skills.tools_loader import _skill_command_registry


# Path to shared schemas (packages/shared/schemas)
def _get_shared_schemas_dir() -> Path:
    """Get the shared schemas directory using project root API."""
    from omni.foundation.runtime.gitops import get_project_root

    return get_project_root() / "packages" / "shared" / "schemas"


SHARED_SCHEMAS_DIR: Path = _get_shared_schemas_dir()
TOOL_SCHEMA_PATH = SHARED_SCHEMAS_DIR / "tool.schema.yaml"


def get_tool_schemas() -> dict[str, Any]:
    """Get schemas for all registered tools from decorator metadata.

    Returns:
        Dictionary mapping tool names to their schemas.
    """
    schemas = {}

    # Get commands from registry populated by @skill_command decorator
    for full_name, func in _skill_command_registry.items():
        config = getattr(func, "_skill_config", None)
        if config:
            schemas[full_name] = _build_tool_schema(full_name, config)

    return schemas


def _build_tool_schema(name: str, config: dict) -> dict[str, Any]:
    """Build a tool schema from its config.

    Args:
        name: Full tool name (e.g., "git.commit")
        config: Tool configuration from @skill_command decorator

    Returns:
        Tool schema dictionary
    """
    # Get variants from registry
    registry = get_variant_registry()
    command_name = name.split(".")[-1] if "." in name else name
    variants = []
    variant_names = registry.list_variants(command_name)

    for var_name in variant_names:
        info = registry.get_info(command_name, var_name)
        if info:
            variants.append(
                {
                    "name": var_name,
                    "description": info.variant_description,
                    "priority": info.variant_priority,
                    "status": info.variant_status.value,
                }
            )

    return {
        "name": config.get("name", name),
        "description": config.get("description", ""),
        "category": config.get("category", "general"),
        "annotations": config.get("annotations", {}),
        "parameters": config.get("input_schema", {}),
        "variants": variants,
        "default_variant": config.get("default_variant"),
        "execution": config.get("execution", {}),
    }


def generate_tool_schemas() -> dict[str, Any]:
    """Generate complete tool schemas document.

    Returns:
        Complete schema document with metadata and all tools.
    """
    tools = []
    schemas = get_tool_schemas()

    for name, schema in schemas.items():
        tool = schema.copy()
        tool["name"] = name
        tools.append(tool)

    return {
        "$schema": "https://omni.dev/schema/tool/v1",
        "info": {
            "name": "Omni-Dev-Fusion MCP Tools",
            "version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "tools": tools,
    }


def export_openapi() -> dict[str, Any]:
    """Export tool schemas in OpenAPI-compatible format.

    Returns:
        OpenAPI-compatible specification.
    """
    schemas = generate_tool_schemas()

    # Convert to OpenAPI format
    openapi = {
        "openapi": "3.1.0",
        "info": schemas["info"],
        "paths": {},
    }

    for tool in schemas["tools"]:
        tool_name = tool["name"]
        parameters = []

        # Convert JSON Schema parameters to OpenAPI
        input_schema = tool.get("parameters", {})
        props = input_schema.get("properties", {})
        required = input_schema.get("required", [])

        openapi_props = {}
        for prop_name, prop_def in props.items():
            openapi_prop = {
                "type": prop_def.get("type", "string"),
                "description": prop_def.get("description", ""),
            }
            if prop_name in required:
                openapi_prop["required"] = True
            if "enum" in prop_def:
                openapi_prop["enum"] = prop_def["enum"]
            if "default" in prop_def:
                openapi_prop["default"] = prop_def["default"]
            openapi_props[prop_name] = openapi_prop

        openapi["paths"][f"/tools/{tool_name}"] = {
            "post": {
                "operationId": tool_name.replace(".", "_"),
                "summary": tool.get("description", ""),
                "description": tool.get("description", ""),
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": openapi_props,
                                "required": required,
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ToolResponse"}
                            }
                        },
                    }
                },
            }
        }

    # Add ToolResponse schema
    openapi["components"] = {
        "schemas": {
            "ToolResponse": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["success", "error", "blocked", "partial"],
                    },
                    "data": {},
                    "error_message": {"type": "string"},
                    "error_code": {"type": "string"},
                    "metadata": {"type": "object"},
                    "timestamp": {"type": "string", "format": "date-time"},
                },
            }
        }
    }

    return openapi


def export_json_schema() -> dict[str, Any]:
    """Export tool schemas as JSON Schema.

    Returns:
        JSON Schema document.
    """
    schemas = generate_tool_schemas()

    # Load the base tool schema (YAML file)
    base_schema: dict[str, Any] = {}
    if TOOL_SCHEMA_PATH.exists():
        try:
            import yaml

            with open(TOOL_SCHEMA_PATH) as f:
                base_schema = yaml.safe_load(f) or {}
        except ImportError:
            # Fallback if PyYAML not available
            pass

    # Combine with generated schemas
    return {
        "$schema": base_schema.get("$schema", "http://json-schema.org/draft-07/schema#"),
        "$id": base_schema.get("$id", "https://omni.dev/schema/tool/v1"),
        "info": schemas["info"],
        "tools": schemas["tools"],
    }


def save_schemas(output_path: str | Path | None = None) -> Path:
    """Save generated schemas to file.

    Args:
        output_path: Output file path (optional)

    Returns:
        Path to saved file.
    """
    schemas = generate_tool_schemas()

    if output_path is None:
        try:
            from omni.foundation.runtime.gitops import get_project_root

            output_path = get_project_root() / "tool_schemas.json"
        except Exception:
            output_path = Path.cwd() / "tool_schemas.json"

    def _json_default(value: Any) -> Any:
        # Decorator metadata may include Python types/classes; encode safely.
        if isinstance(value, type):
            return value.__name__
        return str(value)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schemas, f, indent=2, ensure_ascii=False, default=_json_default)

    return Path(output_path)


def load_schemas(path: str | Path) -> dict[str, Any]:
    """Load tool schemas from file.

    Args:
        path: Path to schema file

    Returns:
        Loaded schema document.
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_tool_schema(tool_name: str) -> dict[str, Any] | None:
    """Get schema for a specific tool.

    Args:
        tool_name: Full tool name (e.g., "git.commit")

    Returns:
        Tool schema or None if not found.
    """
    schemas = get_tool_schemas()
    return schemas.get(tool_name)


def validate_tool_call(tool_name: str, arguments: dict) -> tuple[bool, list[str]]:
    """Validate arguments against tool schema.

    Args:
        tool_name: Full tool name
        arguments: Provided arguments

    Returns:
        Tuple of (is_valid, error_messages)
    """
    schema = get_tool_schema(tool_name)
    if schema is None:
        return False, [f"Tool not found: {tool_name}"]

    errors = []
    params = schema.get("parameters", {})
    props = params.get("properties", {})
    required = params.get("required", [])

    # Check required fields
    for field in required:
        if field not in arguments or arguments.get(field) is None:
            errors.append(f"Missing required field: {field}")

    # Validate types
    for field, value in arguments.items():
        if field in props:
            expected_type = props[field].get("type", "string")
            actual_type = type(value).__name__

            if expected_type == "array" and not isinstance(value, list):
                errors.append(f"Field '{field}': expected {expected_type}, got {actual_type}")
            elif expected_type == "object" and not isinstance(value, dict):
                errors.append(f"Field '{field}': expected {expected_type}, got {actual_type}")

    return len(errors) == 0, errors
