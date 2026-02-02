"""
omni.core.context.tools
Dynamic Tool Schema Injection using Rust-driven Schemas (Schema Singularity).

Transforms internal tool definitions into LLM-compatible formats:
- OpenAI Tool Definition (JSON Schema)
- Anthropic Messages API format
- System prompt descriptions (fallback)

Architecture (Schema Singularity):
    ┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
    │ omni-types      │ ──→ │ RustSchemaRegistry│ ──→ │ LLM (OpenAI/    │
    │ (SSOT for Schema)│     │ (FFI + Cache)     │     │ Anthropic)      │
    └─────────────────┘     └──────────────────┘     └─────────────────┘

Rust is the Single Source of Truth (SSOT) for type definitions.
Python dynamically retrieves authoritative JSON Schemas via FFI.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import structlog
from omni_core_rs import py_get_schema_json

logger = structlog.get_logger(__name__)


class RustSchemaRegistry:
    """
    Cache for Rust-generated JSON Schemas to avoid repetitive FFI calls.

    This establishes Rust as the Single Source of Truth (SSOT) for type definitions.
    Python and LLM consumers retrieve authoritative schemas dynamically.
    """

    _cache: dict[str, dict[str, Any]] = {}

    @classmethod
    def get(cls, type_name: str) -> dict[str, Any]:
        """Get JSON Schema for a type from Rust SSOT."""
        if type_name not in cls._cache:
            schema_json = py_get_schema_json(type_name)
            cls._cache[type_name] = json.loads(schema_json)
        return cls._cache[type_name]

    @classmethod
    def get_skill_definition_schema(cls) -> dict[str, Any]:
        """Get the SkillDefinition schema for tool parameter validation."""
        return cls.get("SkillDefinition")

    @classmethod
    def clear(cls) -> None:
        """Clear the schema cache (useful for testing)."""
        cls._cache.clear()


@dataclass
class ToolDefinition:
    """A tool definition in LLM-compatible format."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_openai(self) -> dict[str, Any]:
        """Convert to OpenAI tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self._ensure_json_schema(),
            },
        }

    def to_anthropic(self) -> dict[str, Any]:
        """Convert to Anthropic tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self._ensure_json_schema(),
        }

    def _ensure_json_schema(self) -> dict[str, Any]:
        """Ensure parameters are valid JSON Schema."""
        if not self.parameters:
            return {
                "type": "object",
                "properties": {},
                "required": [],
            }

        params = self.parameters

        # If it's a Pydantic model with model_json_schema (not a plain dict)
        if not isinstance(params, dict) and hasattr(params, "model_json_schema"):
            return params.model_json_schema()

        # If it's already a dict with type="object"
        if isinstance(params, dict) and params.get("type") == "object":
            return params

        # Wrap in object type
        return {
            "type": "object",
            "properties": params if isinstance(params, dict) else {},
            "required": [],
        }


class ToolContextBuilder:
    """
    Transforms internal tool metadata into LLM-compatible schemas.

    This is the "last mile" connector between the vector database
    and the LLM's tool-calling capability.
    """

    @staticmethod
    def from_metadata(metadata: Any) -> ToolDefinition:
        """Create a ToolDefinition from ToolMetadata."""
        # Handle different metadata formats
        if hasattr(metadata, "name"):  # ToolMetadata or similar object
            name = metadata.name
            description = getattr(metadata, "description", "")
            args = getattr(metadata, "args", [])
            return_type = getattr(metadata, "return_type", "Any")
        elif isinstance(metadata, dict):
            name = metadata.get("name", "")
            description = metadata.get("description", "") or metadata.get("docstring", "")
            args = metadata.get("args", [])
            return_type = metadata.get("return_type", "Any")
        else:
            raise ValueError(f"Unsupported metadata format: {type(metadata)}")

        # Convert args list to JSON Schema properties
        properties = {}
        required_args = []

        for arg in args:
            if isinstance(arg, dict):
                arg_name = arg.get("name", "")
                arg_type = arg.get("type", "string")

                # Convert Python type hints to JSON Schema types
                json_type = _python_type_to_json_schema(arg_type)
                properties[arg_name] = {
                    "type": json_type,
                    "description": arg.get("description", ""),
                }
                required_args.append(arg_name)

        parameters = {
            "type": "object",
            "properties": properties,
            "required": required_args if required_args else [],
        }

        return ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
        )

    @staticmethod
    def to_openai_tools(metadata_list: list[Any]) -> list[dict[str, Any]]:
        """Convert a list of tool metadata to OpenAI format.

        Args:
            metadata_list: List of ToolMetadata from HolographicRegistry

        Returns:
            List of OpenAI tool definitions
        """
        tools = []
        for metadata in metadata_list:
            try:
                tool_def = ToolContextBuilder.from_metadata(metadata)
                tools.append(tool_def.to_openai())
            except Exception as e:
                logger.warning(f"Failed to convert tool to OpenAI format: {e}")
                continue

        return tools

    @staticmethod
    def to_anthropic_tools(metadata_list: list[Any]) -> list[dict[str, Any]]:
        """Convert a list of tool metadata to Anthropic format.

        Args:
            metadata_list: List of ToolMetadata from HolographicRegistry

        Returns:
            List of Anthropic tool definitions
        """
        tools = []
        for metadata in metadata_list:
            try:
                tool_def = ToolContextBuilder.from_metadata(metadata)
                tools.append(tool_def.to_anthropic())
            except Exception as e:
                logger.warning(f"Failed to convert tool to Anthropic format: {e}")
                continue

        return tools

    @staticmethod
    def to_system_prompt(metadata_list: list[Any]) -> str:
        """
        Generate a system prompt section describing available tools.

        This is a fallback for models without native tool support.
        """
        if not metadata_list:
            return "No tools available."

        lines = ["## Available Tools (Dynamically Loaded)", ""]

        for metadata in metadata_list:
            try:
                tool_def = ToolContextBuilder.from_metadata(metadata)

                # Build function signature
                params = tool_def.parameters
                props = params.get("properties", {})
                param_strs = []

                for name, info in props.items():
                    ptype = info.get("type", "any")
                    param_strs.append(f"{name}: {ptype}")

                signature = f"{tool_def.name}({', '.join(param_strs)})"
                lines.append(f"### {tool_def.name}")
                lines.append(f"```python")
                lines.append(f"def {signature} -> Any:")
                lines.append(f'    """{tool_def.description}"""')
                lines.append(f"    ...")
                lines.append(f"```")
                lines.append("")

            except Exception as e:
                logger.debug(f"Failed to format tool for system prompt: {e}")
                continue

        return "\n".join(lines)

    @staticmethod
    def extract_keywords(query: str) -> list[str]:
        """Extract potential keywords from a query for hybrid search.

        Args:
            query: User's natural language query

        Returns:
            List of keywords to boost in hybrid search
        """
        # Simple keyword extraction - split on spaces and filter
        # In a production system, this would use NLP/NER
        words = query.lower().split()

        # Filter out common stopwords
        stopwords = {
            "a",
            "an",
            "the",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "need",
            "dare",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "what",
            "which",
            "who",
            "how",
            "why",
            "where",
            "when",
            "please",
            "help",
            "me",
            "my",
        }

        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        return keywords[:5]  # Limit to top 5 keywords


def _python_type_to_json_schema(python_type: str) -> str:
    """Convert Python type hint to JSON Schema type."""
    type_mapping = {
        "str": "string",
        "string": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "list": "array",
        "dict": "object",
        "any": "string",
        "optional": "string",
        "none": "string",
    }

    # Handle Optional[X] patterns
    if "Optional[" in python_type:
        python_type = python_type.split("[")[1].split("]")[0]

    # Handle List[X] patterns
    if "List[" in python_type:
        return "array"

    return type_mapping.get(python_type.lower(), "string")


# Convenience function for quick tool conversion
def quick_convert(registry_result: list[Any], format: str = "openai") -> str | list[dict[str, Any]]:
    """Quickly convert registry results to LLM format.

    Args:
        registry_result: List of ToolMetadata from registry.search()
        format: Target format ("openai", "anthropic", or "prompt")

    Returns:
        Converted tool definitions (list for "openai"/"anthropic", str for "prompt")
    """
    if format == "openai":
        return ToolContextBuilder.to_openai_tools(registry_result)
    elif format == "anthropic":
        return ToolContextBuilder.to_anthropic_tools(registry_result)
    elif format == "prompt":
        return ToolContextBuilder.to_system_prompt(registry_result)
    else:
        raise ValueError(f"Unknown format: {format}")


# =============================================================================
# Schema Singularity - Direct Rust Schema Access
# =============================================================================


def get_rust_schema(type_name: str) -> dict[str, Any]:
    """
    Get authoritative JSON Schema directly from Rust SSOT.

    Args:
        type_name: Name of the type (e.g., "SkillDefinition", "TaskBrief")

    Returns:
        JSON Schema as a dictionary

    Example:
        schema = get_rust_schema("SkillDefinition")
        print(schema["properties"]["name"]["description"])
    """
    return RustSchemaRegistry.get(type_name)


def list_available_schemas() -> list[str]:
    """
    List all available type schemas from Rust SSOT.

    Returns:
        List of available type names
    """
    from omni_core_rs import py_get_registered_types

    return py_get_registered_types()
