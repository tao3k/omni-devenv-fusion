"""
extract_schema.py - Schema Extractor for @skill_command Functions

This module is part of the agent package and provides schema extraction
for Python functions decorated with @skill_command.

Can be used by:
1. Rust indexer via PyO3 embedding (production)
2. Direct import for debugging/testing
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
import types
from pathlib import Path
from typing import Any

# Constants
PYTHON_TYPE_MAP = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "tuple": "array",
    "None": "null",
}


def python_type_to_json(annotation: Any) -> str:
    """Convert Python type annotation to JSON Schema type."""
    if annotation is None or annotation is type(None):
        return "null"

    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        # Handle Union types (Optional[X] = Union[X, None])
        import typing

        if hasattr(typing, "Union") and origin is typing.Union:
            args = getattr(annotation, "__args__", ())
            for arg in args:
                if arg is not type(None):
                    return python_type_to_json(arg)
            return "null"
        if origin is list:
            return "array"
        if origin is dict:
            return "object"

    type_name = getattr(annotation, "__name__", str(annotation))
    return PYTHON_TYPE_MAP.get(type_name.lower(), "string")


def load_module_isolated(path: Path, skill_name: str) -> types.ModuleType:
    """Load a script module with proper package context.

    This mimics SkillLoaderMixin._load_script_module to ensure skill scripts
    can import from omni.foundation.api.decorators.

    The key is to load the skill's __init__.py first, which registers
    the decorators module and sets up the proper package hierarchy.
    """
    from omni.foundation.config.skills import SKILLS_DIR

    # SSOT: Use SKILLS_DIR to get skills directory
    skills_dir = SKILLS_DIR()

    # Use simple package path for consistency
    pkg_namespace = f"omni.skills.{skill_name}.scripts"
    module_name = f"{pkg_namespace}.{path.stem}"
    parent_package = f"omni.skills.{skill_name}"

    # Ensure parent package exists in sys.modules
    for parent in ["omni", "omni.skills", parent_package]:
        if parent not in sys.modules:
            try:
                import types

                pkg = types.ModuleType(parent)
                sys.modules[parent] = pkg
            except Exception:
                pass

    # First, ensure the parent package (omni.skills.{skill_name}) is registered
    # by loading its __init__.py which typically imports the decorators
    if parent_package not in sys.modules:
        skill_init = skills_dir / skill_name / "__init__.py"
        if skill_init.exists():
            parent_spec = importlib.util.spec_from_file_location(
                parent_package,
                skill_init,
            )
            if parent_spec:
                parent_module = importlib.util.module_from_spec(parent_spec)
                sys.modules[parent_package] = parent_module
                try:
                    parent_spec.loader.exec_module(parent_module)
                except Exception:
                    pass  # Continue even if init fails

    # Also ensure scripts package is registered
    if pkg_namespace not in sys.modules:
        scripts_init = skills_dir / skill_name / "scripts" / "__init__.py"
        if scripts_init.exists():
            package_spec = importlib.util.spec_from_file_location(
                pkg_namespace,
                scripts_init,
            )
            if package_spec:
                package_module = importlib.util.module_from_spec(package_spec)
                package_module.__path__ = [str(scripts_init.parent)]
                sys.modules[pkg_namespace] = package_module
                try:
                    package_spec.loader.exec_module(package_module)
                except Exception:
                    pass

    # Now load the actual script module
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if not spec or not spec.loader:
        raise ImportError(f"Could not load spec for {path}")

    module = importlib.util.module_from_spec(spec)
    module.__package__ = pkg_namespace
    module.__file__ = str(path)

    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def extract_function_schema(file_path: str, func_name: str) -> dict[str, Any]:
    """Extract JSON Schema for a Python function.

    Args:
        file_path: Absolute path to the Python script
        func_name: Name of the function to analyze

    Returns:
        Dictionary containing the JSON Schema
    """
    path = Path(file_path).resolve()
    skill_name = path.parent.parent.name

    try:
        module = load_module_isolated(path, skill_name)

        if not hasattr(module, func_name):
            return {"error": f"Function '{func_name}' not found", "fallback": True}

        func = getattr(module, func_name)
        sig = inspect.signature(func)
        doc = inspect.getdoc(func) or ""

        # Parse docstring for @param descriptions
        param_docs = {}
        if "Args:" in doc or "Parameters:" in doc:
            lines = doc.split("\n")
            for line in lines:
                if line.strip().startswith(("- ", "* ")):
                    param_line = line.strip().lstrip("-* ")
                    if ":" in param_line:
                        param_name = param_line.split(":")[0].strip()
                        param_desc = ":".join(param_line.split(":")[1:]).strip()
                        param_docs[param_name] = param_desc

        properties = {}
        required = []

        for name, param in sig.parameters.items():
            if name in ("self", "cls", "ctx", "context"):
                continue

            param_type = python_type_to_json(param.annotation)
            prop = {"type": param_type, "description": param_docs.get(name, f"Parameter: {name}")}

            if param.default is not inspect.Parameter.empty:
                default_val = param.default
                if not isinstance(default_val, (types.FunctionType, types.MethodType, type)):
                    if default_val is None:
                        prop["default"] = None
                    elif isinstance(default_val, (int, float, bool)):
                        prop["default"] = default_val
                    else:
                        prop["default"] = str(default_val)
            else:
                required.append(name)

            properties[name] = prop

        return {
            "name": func_name,
            "description": doc.split("\n")[0] if doc else f"Execute {func_name}",
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
            "source": {
                "file": str(path),
                "function": func_name,
                "skill": skill_name,
            },
        }

    except Exception as e:
        import traceback

        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "fallback": True,
        }


def extract_schema_to_json(file_path: str, func_name: str) -> str:
    """Convenience function returning JSON string.

    Used by Rust indexer via PyO3.
    """
    import json

    schema = extract_function_schema(file_path, func_name)
    return json.dumps(schema, ensure_ascii=False)


# CLI entry point
if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 3:
        print(
            json.dumps({"error": "Usage: extract_schema.py <file_path> <func_name>"}),
            file=sys.stderr,
        )
        sys.exit(1)

    schema = extract_function_schema(sys.argv[1], sys.argv[2])
    print(json.dumps(schema, ensure_ascii=False))
