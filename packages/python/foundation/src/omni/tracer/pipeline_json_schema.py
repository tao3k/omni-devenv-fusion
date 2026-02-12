"""
pipeline_json_schema.py - JSON Schema for tracer pipeline YAML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jsonschema import Draft202012Validator
from .pipeline_tool_contracts import load_builtin_tool_contracts

PIPELINE_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "servers": {
            "type": "object",
            "patternProperties": {"^[A-Za-z_][A-Za-z0-9_]*$": {"type": "string", "minLength": 1}},
            "additionalProperties": False,
        },
        "parameters": {
            "type": "object",
            "patternProperties": {
                "^[A-Za-z_][A-Za-z0-9_]*$": {},
            },
            "additionalProperties": False,
        },
        "pipeline": {
            "type": "array",
            "minItems": 1,
            "items": {"$ref": "#/$defs/step"},
        },
        "runtime": {"$ref": "#/$defs/runtime"},
    },
    "required": ["pipeline"],
    "additionalProperties": False,
    "$defs": {
        "toolStepConfig": {
            "type": "object",
            "properties": {
                "input": {"type": "object"},
                "output": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                },
            },
            "additionalProperties": False,
        },
        "toolStep": {
            "type": "object",
            "patternProperties": {
                "^[A-Za-z_][A-Za-z0-9_]*\\.[A-Za-z_][A-Za-z0-9_]*$": {
                    "anyOf": [
                        {"type": "null"},
                        {"$ref": "#/$defs/toolStepConfig"},
                    ]
                }
            },
            "minProperties": 1,
            "maxProperties": 1,
            "additionalProperties": False,
        },
        "loopStep": {
            "type": "object",
            "properties": {
                "loop": {
                    "type": "object",
                    "properties": {
                        "max_iterations": {"type": "integer", "minimum": 1},
                        "steps": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"$ref": "#/$defs/step"},
                        },
                    },
                    "required": ["steps"],
                    "additionalProperties": False,
                }
            },
            "required": ["loop"],
            "additionalProperties": False,
        },
        "branchStep": {
            "type": "object",
            "properties": {
                "branch": {
                    "type": "object",
                    "properties": {
                        "router": {"type": "string", "minLength": 1},
                        "field": {"type": "string", "minLength": 1},
                        "value_map": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "array",
                                "items": {"type": "string", "minLength": 1},
                            },
                        },
                        "branches": {
                            "type": "object",
                            "minProperties": 1,
                            "patternProperties": {
                                "^.+$": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"$ref": "#/$defs/step"},
                                }
                            },
                            "additionalProperties": False,
                        },
                    },
                    "required": ["branches"],
                    "additionalProperties": False,
                }
            },
            "required": ["branch"],
            "additionalProperties": False,
        },
        "step": {
            "oneOf": [
                {
                    "type": "string",
                    "pattern": "^[A-Za-z_][A-Za-z0-9_]*\\.[A-Za-z_][A-Za-z0-9_]*$",
                },
                {"$ref": "#/$defs/toolStep"},
                {"$ref": "#/$defs/loopStep"},
                {"$ref": "#/$defs/branchStep"},
            ]
        },
        "runtime": {
            "type": "object",
            "properties": {
                "checkpointer": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["none", "memory"]},
                    },
                    "additionalProperties": False,
                },
                "invoker": {
                    "type": "object",
                    "properties": {
                        "include_retrieval": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "retrieval": {
                    "type": "object",
                    "properties": {
                        "default_backend": {
                            "type": "string",
                            "enum": ["lance", "hybrid"],
                        }
                    },
                    "additionalProperties": False,
                },
                "tracer": {
                    "type": "object",
                    "properties": {
                        "callback_dispatch_mode": {
                            "type": "string",
                            "enum": ["inline", "background"],
                        }
                    },
                    "additionalProperties": False,
                },
                "state": {
                    "type": "object",
                    "properties": {
                        "schema": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "tool_contracts": {
                    "type": "object",
                    "patternProperties": {
                        "^[A-Za-z_][A-Za-z0-9_]*\\.[A-Za-z_][A-Za-z0-9_]*$": {
                            "type": "object",
                            "properties": {
                                "required_input_keys": {
                                    "type": "array",
                                    "items": {"type": "string", "minLength": 1},
                                    "uniqueItems": True,
                                }
                            },
                            "required": ["required_input_keys"],
                            "additionalProperties": False,
                        }
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
    },
}

_VALIDATOR = Draft202012Validator(PIPELINE_JSON_SCHEMA)


def validate_pipeline_schema(data: dict[str, Any]) -> None:
    """Validate raw pipeline payload against JSON Schema."""
    errors = sorted(_VALIDATOR.iter_errors(data), key=lambda e: list(e.path))
    if not errors:
        return

    first = errors[0]
    path = ".".join(str(p) for p in first.path) or "<root>"
    raise ValueError(f"Invalid pipeline schema at `{path}`: {first.message}")


@dataclass(frozen=True)
class ToolContract:
    """Contract for a specific `server.tool` step."""

    required_input_keys: set[str] = field(default_factory=set)


def _get_builtin_registry() -> dict[str, ToolContract]:
    return {
        tool_name: ToolContract(required_input_keys=set(required_keys))
        for tool_name, required_keys in load_builtin_tool_contracts().items()
    }


def validate_pipeline_tool_contracts(data: dict[str, Any]) -> None:
    """Validate known tool step contracts against configured input mappings."""
    registry = _get_builtin_registry()
    builtin_tools = set(registry.keys())
    runtime = data.get("runtime", {})
    if isinstance(runtime, dict):
        custom = runtime.get("tool_contracts", {})
        if isinstance(custom, dict):
            conflicts = sorted(tool for tool in custom.keys() if tool in builtin_tools)
            if conflicts:
                conflict_text = ", ".join(conflicts)
                raise ValueError(
                    "Invalid runtime.tool_contracts: overriding built-in contracts is not allowed "
                    f"({conflict_text})"
                )
            registry.update(_load_custom_contracts(custom))

    pipeline = data.get("pipeline", [])
    if not isinstance(pipeline, list):
        return
    _validate_steps_contracts(pipeline, path="pipeline", registry=registry)


def _validate_steps_contracts(
    steps: list[Any],
    path: str,
    registry: dict[str, ToolContract],
) -> None:
    for index, step in enumerate(steps):
        step_path = f"{path}.{index}"
        if isinstance(step, str):
            # Bare `server.tool` has no input mapping to validate.
            continue
        if not isinstance(step, dict) or len(step) != 1:
            continue

        key, value = next(iter(step.items()))
        if key == "loop" and isinstance(value, dict):
            nested = value.get("steps", [])
            if isinstance(nested, list):
                _validate_steps_contracts(nested, f"{step_path}.loop.steps", registry)
            continue
        if key == "branch" and isinstance(value, dict):
            branches = value.get("branches", {})
            if isinstance(branches, dict):
                for branch_name, branch_steps in branches.items():
                    if isinstance(branch_steps, list):
                        _validate_steps_contracts(
                            branch_steps,
                            f"{step_path}.branch.branches.{branch_name}",
                            registry,
                        )
            continue

        contract = registry.get(key)
        if contract is None:
            continue
        if not isinstance(value, dict):
            continue

        input_mapping = value.get("input", {})
        if not isinstance(input_mapping, dict):
            # Structural type is already enforced by schema validation.
            continue
        present_keys = set(input_mapping.keys())
        missing = sorted(contract.required_input_keys - present_keys)
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(
                f"Invalid tool contract at `{step_path}` for `{key}`: "
                f"missing required input keys: {missing_text}"
            )


def _load_custom_contracts(custom: dict[str, Any]) -> dict[str, ToolContract]:
    loaded: dict[str, ToolContract] = {}
    for tool_name, cfg in custom.items():
        if not isinstance(cfg, dict):
            continue
        required_input_keys = cfg.get("required_input_keys", [])
        if not isinstance(required_input_keys, list):
            continue
        loaded[tool_name] = ToolContract(
            required_input_keys={
                str(item) for item in required_input_keys if isinstance(item, str) and item
            }
        )
    return loaded
