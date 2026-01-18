"""
Unit tests for Phase 62: @skill_command decorator and script-based loading.

Tests the new metadata-driven architecture where scripts/*.py
can be loaded directly without tools.py router layer.
"""

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from agent.skills.decorators import (
    skill_command,
    skill_command,
    is_skill_command,
    get_script_config,
    CommandResult,
)


class TestSkillScriptDecorator:
    """Tests for @skill_command decorator."""

    def test_skill_command_marks_function(self) -> None:
        """Verify @skill_command marks function with marker."""

        @skill_command(description="Test command")
        def test_command(arg1: str) -> str:
            """A test command."""
            return f"Result: {arg1}"

        assert is_skill_command(test_command) is True

    def test_skill_command_stores_config(self) -> None:
        """Verify @skill_command stores config correctly."""

        @skill_command(
            name="custom_name",
            description="A custom command",
            category="write",
            inject_root=True,
        )
        def my_func(arg1: str) -> str:
            """My function docstring."""
            return arg1

        config = get_script_config(my_func)
        assert config is not None
        assert config["name"] == "custom_name"
        assert config["description"] == "A custom command"
        assert config["category"] == "write"
        assert config["inject_root"] is True

    def test_skill_command_defaults(self) -> None:
        """Verify @skill_command has correct defaults."""

        @skill_command()
        def default_func() -> str:
            """A function."""
            return "ok"

        config = get_script_config(default_func)
        assert config is not None
        assert config["name"] == "default_func"
        assert config["category"] == "general"
        assert config["inject_root"] is False
        assert config["max_attempts"] == 3

    def test_skill_command_generates_input_schema(self) -> None:
        """Verify @skill_command generates input schema from type hints."""

        @skill_command(description="Test")
        def typed_func(name: str, count: int = 5) -> str:
            """A typed function."""
            return f"{name}: {count}"

        config = get_script_config(typed_func)
        assert config is not None
        schema = config["input_schema"]
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "count" in schema["properties"]
        assert "name" in schema["required"]

    def test_skill_command_description_from_docstring(self) -> None:
        """Verify @skill_command uses docstring if no description."""

        @skill_command()
        def with_docstring() -> str:
            """This is the description from docstring."""
            return "ok"

        config = get_script_config(with_docstring)
        assert config is not None
        assert config["description"] == "This is the description from docstring."

    # Phase 61: Caching tests
    def test_skill_command_cache_ttl(self) -> None:
        """Verify @skill_command stores cache_ttl in config."""

        @skill_command(
            description="Cached command",
            cache_ttl=60.0,
            pure=True,
        )
        def cached_func() -> str:
            """A cached function."""
            return "result"

        config = get_script_config(cached_func)
        assert config is not None
        assert config["cache_ttl"] == 60.0
        assert config["pure"] is True

    def test_skill_command_cache_defaults(self) -> None:
        """Verify @skill_command has correct caching defaults."""

        @skill_command()
        def uncached_func() -> str:
            """A function without caching."""
            return "result"

        config = get_script_config(uncached_func)
        assert config["cache_ttl"] == 0.0
        assert config["pure"] is False


class TestSkillCommandDecorator:
    """Tests for existing @skill_command (ensure backward compatibility)."""

    def test_skill_command_still_works(self) -> None:
        """Verify @skill_command continues to work."""

        @skill_command(description="Test", category="test")
        def test_cmd() -> str:
            """A test command."""
            return "ok"

        assert hasattr(test_cmd, "_is_skill_command")
        assert hasattr(test_cmd, "_skill_config")

    def test_skill_command_returns_direct_result(self) -> None:
        """Verify @skill_command returns result directly (no wrapper)."""

        @skill_command()
        def simple() -> str:
            """Simple function."""
            return "result"

        # Call the decorated function - returns result directly
        result = simple()
        assert result == "result"
        # The function is not wrapped, returns raw result
        assert not isinstance(result, CommandResult)


class TestSkillScriptExecution:
    """Tests for executing @skill_command decorated functions."""

    @pytest.fixture
    def sample_script_module(self, tmp_path: Path) -> ModuleType:
        """Create a mock script module for testing."""
        # Create a temporary script file
        script_content = '''
from agent.skills.decorators import skill_command

@skill_command(description="Echo a message", category="general")
def echo(message: str) -> str:
    """Echo the message back."""
    return f"Echo: {message}"

@skill_command(description="Add numbers", category="general", inject_root=True)
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''
        script_file = tmp_path / "test_script.py"
        script_file.write_text(script_content)

        # Load the module
        spec = importlib.util.spec_from_file_location("test_script", script_file)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return module

    def test_extract_script_commands(
        self,
        sample_script_module: ModuleType,
    ) -> None:
        """Verify we can extract commands from a script module."""
        from agent.core.skill_runtime.support.loader import SkillLoaderMixin

        class TestLoader(SkillLoaderMixin):
            skills_dir = Path(".")

        loader = TestLoader()
        commands = loader._extract_script_commands(sample_script_module, "test_skill")

        assert "echo" in commands
        assert "add" in commands

        echo_cmd = commands["echo"]
        assert echo_cmd.description == "Echo a message"
        assert echo_cmd._script_mode is True

    def test_script_command_input_schema(
        self,
        sample_script_module: ModuleType,
    ) -> None:
        """Verify script commands have correct input schema."""
        from agent.core.skill_runtime.support.loader import SkillLoaderMixin

        class TestLoader(SkillLoaderMixin):
            skills_dir = Path(".")

        loader = TestLoader()
        commands = loader._extract_script_commands(sample_script_module, "test_skill")

        echo_schema = commands["echo"].input_schema
        assert "message" in echo_schema["properties"]
        assert echo_schema["properties"]["message"]["type"] == "string"


class TestSkillCommandScriptMode:
    """Tests for SkillCommand in script mode."""

    def test_skill_command_script_mode_fields(self) -> None:
        """Verify SkillCommand accepts script mode fields."""
        from agent.core.skill_runtime.support.models import SkillCommand

        def dummy_func() -> str:
            return "ok"

        cmd = SkillCommand(
            name="test",
            func=dummy_func,
            description="Test command",
            _script_mode=True,
            _inject_root=True,
            _inject_settings=["git.user"],
            _retry_on=(ConnectionError,),
            _max_attempts=5,
        )

        assert cmd._script_mode is True
        assert cmd._inject_root is True
        assert "git.user" in cmd._inject_settings
        assert cmd._max_attempts == 5

    @pytest.mark.asyncio
    async def test_skill_command_script_mode_injects_root(self) -> None:
        """Verify script mode injects project_root when requested."""
        from agent.core.skill_runtime.support.models import SkillCommand
        from pathlib import Path

        captured_args: dict = {}

        def capture_args(project_root: Path = None) -> str:
            captured_args["project_root"] = project_root
            return "ok"

        # Mock get_project_root at the source module where it's imported
        with patch("common.config_paths.get_project_root", return_value=Path("/mock/project")):
            cmd = SkillCommand(
                name="test",
                func=capture_args,
                description="Test",
                _script_mode=True,
                _inject_root=True,
            )

            await cmd.execute({})

            assert "project_root" in captured_args
            assert captured_args["project_root"] is not None
            assert isinstance(captured_args["project_root"], Path)
