"""
schema.py - Pydantic V2 Schema Generation

Provides automatic OpenAPI/JSON Schema generation from function signatures.
Uses Pydantic V2 create_model for type-safe schema generation.
"""

from __future__ import annotations

import inspect
import types
from collections.abc import Callable
from typing import Any, get_type_hints

from pydantic import Field, create_model

from ..config.logging import get_logger

logger = get_logger("omni.api.schema")


def _generate_tool_schema(func: Callable, exclude_params: set[str] | None = None) -> dict[str, Any]:
    """
    [Core Algorithm] Auto-generate OpenAPI Schema using Pydantic V2 reflection.

    Principle:
    1. Analyze function signature and type annotations.
    2. Dynamically build a Pydantic Model (create_model) to represent parameter structure.
    3. Export standard Schema via .model_json_schema().
    """
    if exclude_params is None:
        exclude_params = set()

    sig = inspect.signature(func)

    # Get resolved type hints (handles ForwardRef, etc.)
    try:
        type_hints = get_type_hints(func, include_extras=True)
    except Exception:
        # Fallback to raw annotations if type resolution fails
        type_hints = {n: p.annotation for n, p in sig.parameters.items()}

    # Lazy import Settings to avoid circular dependency
    from ..config.paths import ConfigPaths
    from ..config.settings import Settings

    # Build a set of types to exclude from schema generation
    _INJECTED_TYPES_SET = {Settings, ConfigPaths}

    fields = {}

    for param_name, param in sig.parameters.items():
        # 1. Filter out dependency injection params (e.g., project_root) and *args/**kwargs
        if param_name in exclude_params or param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        annotation = type_hints.get(param_name, Any)

        # Get origin and args for type analysis
        # Handle both typing.Union and types.UnionType (Python 3.12+ X | None syntax)
        is_union_type = isinstance(annotation, types.UnionType)
        origin = getattr(annotation, "__origin__", None)
        args = getattr(annotation, "__args__", ())

        # 2. Filter out infrastructure types that can't be serialized by Pydantic
        # Handle both direct type matches and Union types (e.g., Settings | None)
        is_injected = annotation in _INJECTED_TYPES_SET
        if not is_injected and (is_union_type or origin is not None):
            # Check if any arg in the Union is an injected type
            non_injected_args = [a for a in args if a is not type(None)]
            is_injected = any(arg in _INJECTED_TYPES_SET for arg in non_injected_args)
            if is_injected:
                continue
            # Resolve Optional[X] to X for non-injected types
            if None in args and non_injected_args:
                annotation = non_injected_args[0]
                origin = getattr(annotation, "__origin__", None)
                args = getattr(annotation, "__args__", ())

        # 3. Handle Literal types - create enum
        if origin is not None and hasattr(annotation, "__args__"):
            # Literal["value1", "value2"] -> enum
            import typing

            if getattr(annotation, "_name", None) == "Literal" or origin is typing.Literal:
                literal_args = annotation.__args__
                if all(isinstance(a, (str, int, float)) for a in literal_args):
                    # Create a dynamic enum-like annotation
                    annotation = type(
                        f"Literal_{param_name}", (), {"__args__": literal_args, "_name": "Literal"}
                    )

        # 4. Handle list[...] and dict[...] generics
        if origin is not None:
            if hasattr(annotation, "_name") and annotation._name in ("List", "list"):
                # list[T] -> array with items
                item_args = getattr(annotation, "__args__", ())
                if item_args:
                    item_type = item_args[0] if not isinstance(item_args[0], type(None)) else Any
                    if isinstance(item_type, type) and not hasattr(item_type, "__annotations__"):
                        annotation = list
                else:
                    annotation = list

        # 5. Build field kwargs (description from docstring)
        field_kwargs: dict[str, Any] = {}

        # Extract description from docstring for this parameter
        docstring = func.__doc__ or ""
        param_pattern = f":param {param_name}:"
        param_default_pattern = f":param {param_name} "

        if docstring and (param_pattern in docstring or param_default_pattern in docstring):
            import re

            # Try to find the line with :param name:
            pattern = rf"(?:^|\n)\s*:param\s+{param_name}\s*:\s*(.+?)(?=\n\s*:param|\n\s*\w|\Z)"
            match = re.search(pattern, docstring, re.DOTALL | re.IGNORECASE)
            if match:
                desc = match.group(1).strip()
                # Remove newlines and extra spaces
                desc = " ".join(desc.split())
                if desc:
                    field_kwargs["description"] = desc

        # Add default value if present
        if param.default is not inspect.Parameter.empty:
            field_kwargs["default"] = param.default

        # Build the field - use actual annotation for proper type inference
        try:
            fields[param_name] = (annotation, Field(**field_kwargs))
        except Exception:
            # Fallback: use Any if annotation causes issues
            fields[param_name] = (Any, Field(**field_kwargs))
            logger.debug(f"Failed to add field {param_name} to schema for {func.__name__}")

    # Create a temporary Pydantic model just to extract the JSON Schema
    # This is a standard Pydantic V2 pattern for schema extraction
    try:
        TempModel = create_model(
            f"Temp_{func.__name__}_Params",
            **fields,  # type: ignore[arg-type]
        )
        schema = TempModel.model_json_schema()
    except Exception as e:
        logger.warning(f"Failed to create Pydantic model for {func.__name__}: {e}")
        # Fallback to minimal schema
        return {"type": "object", "properties": {}, "required": []}

    # Clean up schema - remove the model name
    schema.pop("title", None)
    schema.pop("$schema", None)

    # Build required list from parameter kinds
    required = []
    for param_name, param in sig.parameters.items():
        if param_name in exclude_params:
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    # Always include required field to explicitly declare which params are needed
    # This helps LLM understand the function signature correctly
    schema["required"] = required

    return schema


__all__ = [
    "_generate_tool_schema",
]
