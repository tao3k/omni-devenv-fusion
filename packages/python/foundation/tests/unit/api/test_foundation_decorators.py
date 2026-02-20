"""
Tests for omni.foundation.api.decorators (Pydantic-Powered Macros)

Tests cover:
- @skill_command decorator with auto schema generation
- @inject_resources dependency injection
- Schema generation with various type annotations
- Settings/ConfigPaths exclusion from schema
- Union types handling (Optional[X], X | None)
- CommandResult return type handling

Usage:
    python -m pytest packages/python/foundation/tests/unit/api/test_foundation_decorators.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from omni.foundation.api.decorators import (
    get_script_config,
    inject_resources,
    is_mcp_canonical_result,
    is_skill_command,
    normalize_mcp_tool_result,
    skill_command,
)
from omni.foundation.api.types import CommandResult
from omni.foundation.config.paths import ConfigPaths
from omni.foundation.config.settings import Settings

# =============================================================================
# Test Fixtures and Helper Functions
# =============================================================================


class TestSkillCommandDecorator:
    """Tests for @skill_command decorator."""

    def test_basic_skill_command(self):
        """Test basic @skill_command without type hints."""

        @skill_command(name="test_command", description="A test command")
        def test_func() -> dict:
            """A simple test function."""
            return {"success": True}

        assert is_skill_command(test_func) is True
        config = get_script_config(test_func)
        assert config["name"] == "test_command"
        # Description uses decorator param if provided, falls back to docstring
        assert config["description"] == "A test command"
        assert config["category"] == "general"

    def test_skill_command_with_input_schema(self):
        """Test that input_schema is generated correctly."""

        @skill_command(name="echo", description="Echo a message")
        def echo(message: str, count: int = 1) -> dict:
            """Echo a message multiple times."""
            return {"message": message * count}

        config = get_script_config(echo)
        schema = config["input_schema"]

        assert schema["type"] == "object"
        assert "message" in schema["properties"]
        assert "count" in schema["properties"]
        # message is required (no default), count has default
        assert "message" in schema.get("required", [])

    def test_skill_command_with_path_type(self):
        """Test @skill_command with Path type annotation."""

        @skill_command(name="read_file", description="Read a file")
        def read_file(path: Path, encoding: str = "utf-8") -> dict:
            """Read file contents."""
            return {"path": str(path)}

        config = get_script_config(read_file)
        schema = config["input_schema"]

        assert "path" in schema["properties"]
        assert "encoding" in schema["properties"]

    def test_skill_command_with_optional_path(self):
        """Test @skill_command with optional Path."""

        @skill_command(name="process", description="Process a file")
        def process(
            input_path: Path | None = None,
            output_path: Path | None = None,
        ) -> dict:
            """Process files."""
            return {"input": str(input_path)}

        config = get_script_config(process)
        schema = config["input_schema"]

        # Both optional params should have defaults
        assert schema["properties"]["input_path"].get("default") is None
        assert schema["properties"]["output_path"].get("default") is None

    def test_skill_command_category(self):
        """Test @skill_command with custom category."""

        @skill_command(
            name="admin_task",
            category="admin",
            description="An admin task",
        )
        def admin_func() -> dict:
            """Admin function."""
            return {}

        config = get_script_config(admin_func)
        assert config["category"] == "admin"

    def test_skill_command_execution_config(self):
        """Test @skill_command execution configuration."""

        @skill_command(
            name="retry_task",
            retry_on=(ValueError,),
            max_attempts=3,
            cache_ttl=60.0,
        )
        def retry_func() -> dict:
            """Function with retry config."""
            return {}

        config = get_script_config(retry_func)
        exec_config = config["execution"]
        assert exec_config["retry_on"] == (ValueError,)
        assert exec_config["max_attempts"] == 3
        assert exec_config["cache_ttl"] == 60.0

    def test_skill_command_inject_root(self):
        """Test @skill_command with inject_root."""

        @skill_command(
            name="with_root",
            inject_root=True,
            description="Function that gets project root",
        )
        def with_root(project_root: Path) -> dict:
            """Function with project root injection."""
            return {"root": str(project_root)}

        config = get_script_config(with_root)
        exec_config = config["execution"]
        assert exec_config["inject_root"] is True

    def test_skill_command_autowire(self):
        """Test @skill_command autowire default is True."""

        @skill_command(name="autowire_test")
        def autowire_func() -> dict:
            """Test autowire."""
            return {}

        config = get_script_config(autowire_func)
        assert config["execution"]["autowire"] is True

    def test_skill_command_without_parentheses(self):
        """Test @skill_command can be used without parentheses."""

        @skill_command
        def simple_func() -> dict:
            """A simple function."""
            return {}

        assert is_skill_command(simple_func) is True
        config = get_script_config(simple_func)
        assert config["name"] == "simple_func"

    def test_skill_command_with_command_result(self):
        """Test @skill_command with CommandResult return type."""

        @skill_command(name="result_test")
        def result_func(value: int) -> CommandResult[dict]:
            """Return CommandResult."""
            return CommandResult(success=True, data={"value": value})

        config = get_script_config(result_func)
        # Schema should include 'value' parameter
        assert "value" in config["input_schema"]["properties"]


class TestSettingsExclusionFromSchema:
    """Tests for Settings type exclusion from schema generation.

    These tests verify that Settings and ConfigPaths types are properly
    excluded from the JSON schema (they are injected at runtime).
    """

    def test_settings_parameter_excluded_from_schema(self):
        """Test that Settings type is excluded from schema."""

        @skill_command(name="with_settings")
        def func_with_settings(
            message: str,
            settings: Settings | None = None,
        ) -> dict:
            """Function with Settings injection."""
            return {"message": message}

        config = get_script_config(func_with_settings)
        schema = config["input_schema"]

        # message should be in schema, settings should be excluded
        assert "message" in schema["properties"]
        assert "settings" not in schema["properties"]

    def test_configpaths_parameter_excluded_from_schema(self):
        """Test that ConfigPaths type is excluded from schema."""

        @skill_command(name="with_paths")
        def func_with_paths(
            filename: str,
            paths: ConfigPaths | None = None,
        ) -> dict:
            """Function with ConfigPaths injection."""
            return {"filename": filename}

        config = get_script_config(func_with_paths)
        schema = config["input_schema"]

        # filename should be in schema, paths should be excluded
        assert "filename" in schema["properties"]
        assert "paths" not in schema["properties"]

    def test_multiple_injected_types_excluded(self):
        """Test that both Settings and ConfigPaths are excluded."""

        @skill_command(name="full_injection")
        def fully_injected(
            name: str,
            settings: Settings | None = None,
            paths: ConfigPaths | None = None,
        ) -> dict:
            """Function with multiple injected types."""
            return {"name": name}

        config = get_script_config(fully_injected)
        schema = config["input_schema"]

        # Only 'name' should be in schema
        assert "name" in schema["properties"]
        assert "settings" not in schema["properties"]
        assert "paths" not in schema["properties"]
        assert "required" not in schema or "name" in schema.get("required", [])

    def test_settings_without_none_default(self):
        """Test Settings type without None default is still excluded."""

        @skill_command(name="settings_no_default")
        def func_settings_no_default(
            value: int,
            settings: Settings,  # No None default
        ) -> dict:
            """Function with Settings but no None default."""
            return {"value": value}

        config = get_script_config(func_settings_no_default)
        schema = config["input_schema"]

        # settings should still be excluded
        assert "settings" not in schema["properties"]
        assert "value" in schema["properties"]


class TestUnionTypesHandling:
    """Tests for Union type handling in schema generation."""

    def test_optional_string_parameter(self):
        """Test Optional[str] (typing.Optional) parameter."""

        @skill_command(name="optional_str")
        def func_optional_str(
            name: str | None = None,
        ) -> dict:
            """Function with optional string."""
            return {"name": name}

        config = get_script_config(func_optional_str)
        schema = config["input_schema"]

        assert "name" in schema["properties"]
        assert schema["properties"]["name"].get("default") is None

    def test_optional_int_parameter(self):
        """Test Optional[int] parameter."""

        @skill_command(name="optional_int")
        def func_optional_int(
            count: int | None = None,
        ) -> dict:
            """Function with optional int."""
            return {"count": count}

        config = get_script_config(func_optional_int)
        schema = config["input_schema"]

        assert "count" in schema["properties"]
        assert schema["properties"]["count"].get("default") is None

    def test_mixed_required_and_optional(self):
        """Test function with both required and optional parameters."""

        @skill_command(name="mixed_params")
        def func_mixed(
            required_param: str,
            optional_param: int | None = None,
        ) -> dict:
            """Function with mixed params."""
            return {}

        config = get_script_config(func_mixed)
        schema = config["input_schema"]

        # Both should be in properties
        assert "required_param" in schema["properties"]
        assert "optional_param" in schema["properties"]
        # Only required_param should be in required
        assert "required_param" in schema.get("required", [])
        assert "optional_param" not in schema.get("required", [])

    def test_union_without_none(self):
        """Test Union type without None (non-optional)."""

        @skill_command(name="union_no_none")
        def func_union_no_none(
            value: str | int,
        ) -> dict:
            """Function with non-optional Union."""
            return {"value": value}

        config = get_script_config(func_union_no_none)
        schema = config["input_schema"]

        # value should be in schema
        assert "value" in schema["properties"]


class TestInjectResourcesDecorator:
    """Tests for @inject_resources decorator."""

    def test_inject_resources_basic(self):
        """Test basic @inject_resources functionality."""

        @inject_resources
        def func_with_settings(settings: Settings) -> str:
            """Function that uses Settings."""
            return "ok" if settings else "fail"

        # Function should be wrapped
        assert callable(func_with_settings)

    def test_inject_resources_with_type_hints(self):
        """Test @inject_resources preserves type hints."""

        @inject_resources
        def func_types(
            s: Settings,
            p: ConfigPaths,
            name: str,
        ) -> dict:
            """Function with multiple types."""
            return {"name": name}

        # The wrapped function should still be callable
        # (actual injection happens at runtime)
        # Annotations are preserved (as strings in Python 3.13+)
        annotations = func_types.__annotations__
        assert "s" in annotations
        assert "Settings" in str(annotations["s"]) or "Settings" in annotations["s"]

    def test_inject_resources_no_params(self):
        """Test @inject_resources with no params to inject."""

        @inject_resources
        def simple_func(x: int, y: int) -> int:
            """Function without injectable params."""
            return x + y

        # Should return original function
        assert simple_func(1, 2) == 3


class TestSchemaGenerationEdgeCases:
    """Edge case tests for schema generation."""

    def test_empty_function(self):
        """Test @skill_command with no parameters."""

        @skill_command(name="empty_func")
        def empty_func() -> dict:
            """Empty function."""
            return {}

        config = get_script_config(empty_func)
        schema = config["input_schema"]

        assert schema["type"] == "object"
        assert schema["properties"] == {}
        assert schema.get("required", []) == []

    def test_all_defaults(self):
        """Test function where all params have defaults."""

        @skill_command(name="all_defaults")
        def all_defaults(
            a: int = 1,
            b: str = "test",
            c: bool = True,
        ) -> dict:
            """Function with all defaults."""
            return {}

        config = get_script_config(all_defaults)
        schema = config["input_schema"]

        # All params should be in properties with defaults
        assert "a" in schema["properties"]
        assert "b" in schema["properties"]
        assert "c" in schema["properties"]
        # No required params
        assert schema.get("required", []) == []

    def test_list_parameter(self):
        """Test function with list parameter."""

        @skill_command(name="with_list")
        def with_list(items: list[str], count: int = 1) -> dict:
            """Function with list param."""
            return {"items": items[:count]}

        config = get_script_config(with_list)
        schema = config["input_schema"]

        assert "items" in schema["properties"]
        assert "count" in schema["properties"]

    def test_dict_parameter(self):
        """Test function with dict parameter."""

        @skill_command(name="with_dict")
        def with_dict(config: dict[str, Any], key: str) -> dict:
            """Function with dict param."""
            return {"value": config.get(key)}

        config = get_script_config(with_dict)
        schema = config["input_schema"]

        assert "config" in schema["properties"]
        assert "key" in schema["properties"]

    def test_complex_nested_types(self):
        """Test function with complex nested type annotations."""

        @skill_command(name="complex_types")
        def complex_types(
            items: list[dict[str, Any]],
            mapping: dict[str, list[int]],
            pair: tuple[str, int],
        ) -> dict:
            """Function with complex types."""
            return {}

        config = get_script_config(complex_types)
        schema = config["input_schema"]

        # All params should be in schema
        assert "items" in schema["properties"]
        assert "mapping" in schema["properties"]
        assert "pair" in schema["properties"]


class TestCommandResultSchema:
    """Tests for CommandResult in schema context."""

    def test_command_result_not_in_params(self):
        """Test that CommandResult is not treated as input param."""

        @skill_command(name="cmd_result_test")
        def cmd_result(value: int) -> CommandResult[dict]:
            """Function returning CommandResult."""
            return CommandResult(success=True, data={"v": value})

        config = get_script_config(cmd_result)
        schema = config["input_schema"]

        # Only 'value' should be in schema, not CommandResult
        assert "value" in schema["properties"]
        assert "CommandResult" not in str(schema)

    def test_command_result_generic_type(self):
        """Test CommandResult with generic type parameter."""

        @skill_command(name="typed_result")
        def typed_result(data: list[str]) -> CommandResult[list[str]]:
            """Function returning typed CommandResult."""
            return CommandResult(success=True, data=data)

        config = get_script_config(typed_result)
        schema = config["input_schema"]

        # 'data' param should be in schema
        assert "data" in schema["properties"]


class TestDecoratorMetadata:
    """Tests for decorator metadata attachment."""

    def test_skill_command_attaches_metadata(self):
        """Test that @skill_command attaches required metadata."""

        @skill_command(
            name="metadata_test",
            description="Test metadata attachment",
            category="test",
        )
        def metadata_func() -> dict:
            """Test function."""
            return {}

        assert hasattr(metadata_func, "_is_skill_command")
        assert hasattr(metadata_func, "_skill_config")
        assert metadata_func._is_skill_command is True

    def test_skill_config_contains_all_fields(self):
        """Test that _skill_config contains all expected fields."""

        @skill_command(
            name="full_config_test",
            description="Full config test",
            category="test",
            inject_root=True,
        )
        def full_config_func(project_root: Path) -> dict:
            """Full config test function."""
            return {}

        config = get_script_config(full_config_func)

        assert "name" in config
        assert "description" in config
        assert "category" in config
        assert "input_schema" in config
        assert "execution" in config

        execution = config["execution"]
        assert "inject_root" in execution
        assert execution["inject_root"] is True

    def test_description_from_docstring(self):
        """Test that description is extracted from docstring."""

        @skill_command
        def docstring_test() -> dict:
            """This is my custom docstring description."""
            return {}

        config = get_script_config(docstring_test)
        assert config["description"] == "This is my custom docstring description."

    def test_default_skill_command_keeps_handler_disabled(self):
        """Default decorator args should not enable execution handler config."""

        @skill_command(name="default_handler_off")
        def default_handler_off() -> dict:
            """Default handler config test."""
            return {"ok": True}

        config = get_script_config(default_handler_off)
        assert config["execution"]["handler"] is None

    def test_skill_command_records_execution_phase(self, monkeypatch: pytest.MonkeyPatch):
        """Decorator wrapper should emit skill_command.execute phase timing."""
        captured: dict[str, Any] = {}

        def _fake_record_phase(phase: str, duration_ms: float, **extra: Any) -> None:
            captured["phase"] = phase
            captured["duration_ms"] = duration_ms
            captured["extra"] = extra

        monkeypatch.setattr(
            "omni.foundation.runtime.skills_monitor.record_phase",
            _fake_record_phase,
        )

        @skill_command(name="phase_probe")
        def phase_probe(value: int) -> dict:
            """Probe skill_command monitor phase."""
            return {"value": value}

        _ = phase_probe(1)

        assert captured["phase"] == "skill_command.execute"
        assert captured["extra"]["tool"] == "general.phase_probe"
        assert captured["extra"]["function"] == "phase_probe"
        assert captured["extra"]["success"] is True
        assert captured["duration_ms"] >= 0

    def test_skill_command_records_execution_failure_for_error_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Decorator monitor success should be false when normalized MCP payload is error."""
        captured: dict[str, Any] = {}

        def _fake_record_phase(phase: str, duration_ms: float, **extra: Any) -> None:
            captured["phase"] = phase
            captured["duration_ms"] = duration_ms
            captured["extra"] = extra

        monkeypatch.setattr(
            "omni.foundation.runtime.skills_monitor.record_phase",
            _fake_record_phase,
        )

        @skill_command(name="phase_probe_error")
        def phase_probe_error() -> dict:
            """Probe error payload."""
            return {"content": [{"type": "text", "text": "failed"}], "isError": True}

        _ = phase_probe_error()

        assert captured["phase"] == "skill_command.execute"
        assert captured["extra"]["tool"] == "general.phase_probe_error"
        assert captured["extra"]["function"] == "phase_probe_error"
        assert captured["extra"]["success"] is False
        assert captured["duration_ms"] >= 0

    def test_skill_command_records_execution_failure_for_error_status_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Decorator monitor success should be false when payload status is error."""
        captured: dict[str, Any] = {}

        def _fake_record_phase(phase: str, duration_ms: float, **extra: Any) -> None:
            captured["phase"] = phase
            captured["duration_ms"] = duration_ms
            captured["extra"] = extra

        monkeypatch.setattr(
            "omni.foundation.runtime.skills_monitor.record_phase",
            _fake_record_phase,
        )

        @skill_command(name="phase_probe_status_error")
        def phase_probe_status_error() -> str:
            """Probe status error payload."""
            return '{"status":"error","error":"boom","results":[]}'

        _ = phase_probe_status_error()

        assert captured["phase"] == "skill_command.execute"
        assert captured["extra"]["tool"] == "general.phase_probe_status_error"
        assert captured["extra"]["function"] == "phase_probe_status_error"
        assert captured["extra"]["success"] is False
        assert captured["duration_ms"] >= 0

    def test_skill_command_records_graph_stats_meta_fields(self, monkeypatch: pytest.MonkeyPatch):
        """Decorator monitor should emit graph stats meta fields when present in payload."""
        captured: dict[str, Any] = {}

        def _fake_record_phase(phase: str, duration_ms: float, **extra: Any) -> None:
            captured["phase"] = phase
            captured["duration_ms"] = duration_ms
            captured["extra"] = extra

        monkeypatch.setattr(
            "omni.foundation.runtime.skills_monitor.record_phase",
            _fake_record_phase,
        )

        @skill_command(name="phase_probe_graph_meta")
        def phase_probe_graph_meta() -> dict:
            return {
                "success": True,
                "graph_stats": {"total_notes": 337},
                "graph_stats_meta": {
                    "source": "cache",
                    "cache_hit": True,
                    "fresh": True,
                    "age_ms": 12,
                    "refresh_scheduled": False,
                },
            }

        _ = phase_probe_graph_meta()

        assert captured["phase"] == "skill_command.execute"
        assert captured["extra"]["graph_stats_source"] == "cache"
        assert captured["extra"]["graph_stats_cache_hit"] is True
        assert captured["extra"]["graph_stats_fresh"] is True
        assert captured["extra"]["graph_stats_age_ms"] == 12
        assert captured["extra"]["graph_stats_refresh_scheduled"] is False
        assert captured["extra"]["graph_stats_total_notes"] == 337


class TestDecoratorEdgeCases:
    """Additional edge case tests."""

    def test_decorator_preserves_function_name(self):
        """Test that decorator preserves original function name."""

        @skill_command(name="renamed")
        def my_original_function() -> dict:
            """Docstring."""
            return {}

        assert my_original_function.__name__ == "my_original_function"

    def test_decorator_preserves_docstring(self):
        """Test that decorator preserves original docstring."""

        @skill_command(name="doc_preserved")
        def my_function() -> dict:
            """My original docstring."""
            return {}

        assert my_function.__doc__ == "My original docstring."

    def test_decorator_preserves_function_annotations(self):
        """Test that function annotations are preserved."""

        @skill_command(name="annotations_test")
        def annotated_func(x: int, y: str) -> bool:
            """Annotated function."""
            return True

        # In Python 3.13+, annotations are stored as strings
        annotations = annotated_func.__annotations__
        assert "x" in annotations
        assert "int" in str(annotations["x"]) or annotations["x"] == int
        assert "y" in annotations
        assert "str" in str(annotations["y"]) or annotations["y"] == str
        assert "return" in annotations

    def test_skill_command_execution_settings(self):
        """Test execution settings are properly stored."""

        @skill_command(
            name="exec_test",
            inject_settings=["api.key", "debug"],
        )
        def exec_settings_func() -> dict:
            """Function with inject settings."""
            return {}

        config = get_script_config(exec_settings_func)
        exec_config = config["execution"]

        assert "inject_settings" in exec_config
        assert exec_config["inject_settings"] == ["api.key", "debug"]


def test_mcp_tool_result_validates_against_shared_schema():
    """Normalized MCP tool results must conform to shared schema (mcp_schema API, CI drift guard)."""
    from omni.foundation.api.mcp_schema import get_schema_path, validate

    if not get_schema_path().exists():
        pytest.skip("Shared schema not found (project_root may be overridden in this worker)")
    for raw in [None, "ok", {"k": "v"}, [1, 2]]:
        result = normalize_mcp_tool_result(raw)
        assert is_mcp_canonical_result(result)
        validate(result)


def test_normalize_mcp_tool_result_strips_extra_keys():
    """Canonical-shaped return with extra keys (e.g. 'result') must be stripped to schema-only."""
    from omni.foundation.api.mcp_schema import CONTENT_KEY, IS_ERROR_KEY

    canonical_with_extra = {
        CONTENT_KEY: [{"type": "text", "text": "ok"}],
        IS_ERROR_KEY: False,
        "result": {"nested": "data"},
        "method": "tools/call",
    }
    out = normalize_mcp_tool_result(canonical_with_extra)
    assert list(out.keys()) == [CONTENT_KEY, IS_ERROR_KEY]
    assert out[CONTENT_KEY] == [{"type": "text", "text": "ok"}]
    assert out[IS_ERROR_KEY] is False
