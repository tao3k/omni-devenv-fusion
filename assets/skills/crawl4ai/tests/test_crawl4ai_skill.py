"""
Tests for crawl4ai skill.

Tests cover:
- @skill_command decorator attributes (utils.py)
- Command registration via script_loader
- Isolation pattern integration
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCrawl4aiUtilsDecorator:
    """Tests for the utils.py skill_command decorator."""

    def test_decorator_sets_is_skill_command_attr(self):
        """Test that decorator sets _is_skill_command to True."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.utils import skill_command

        @skill_command(name="test_cmd", description="Test command")
        async def test_func():
            pass

        assert getattr(test_func, "_is_skill_command", False) is True

    def test_decorator_sets_skill_config_attr(self):
        """Test that decorator sets _skill_config with kwargs."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.utils import skill_command

        @skill_command(
            name="crawl_url",
            description="Crawl a web page",
            category="read",
        )
        async def crawl_func():
            pass

        config = getattr(crawl_func, "_skill_config", None)
        assert config is not None
        assert config["name"] == "crawl_url"
        assert config["description"] == "Crawl a web page"
        assert config["category"] == "read"

    def test_decorator_preserves_function_signature(self):
        """Test that decorator preserves async function signature."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.utils import skill_command

        @skill_command(name="test", description="Test")
        async def my_func(url: str, fit_markdown: bool = True):
            """My docstring."""
            return url

        # Check function name is preserved
        assert my_func.__name__ == "my_func"
        # Check docstring is preserved
        assert "My docstring" in my_func.__doc__


class TestCrawl4aiCommands:
    """Tests for crawl4ai command registration."""

    def test_crawl_url_function_exists(self):
        """Test that crawl_url function is importable."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.crawl_url import crawl_url

        assert callable(crawl_url)

    def test_crawl_url_has_skill_command_attr(self):
        """Test that crawl_url has _is_skill_command attribute."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.crawl_url import crawl_url

        assert getattr(crawl_url, "_is_skill_command", False) is True

    def test_crawl_url_has_skill_config(self):
        """Test that crawl_url has _skill_config with name 'crawl_url'."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.crawl_url import crawl_url

        config = getattr(crawl_url, "_skill_config", None)
        assert config is not None
        assert config.get("name") == "crawl_url"

    @pytest.mark.asyncio
    async def test_crawl_url_rejects_invalid_action(self, monkeypatch):
        """Invalid action should return standardized validation payload."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.crawl_url import CrawlUrl

        from omni.foundation.api.mcp_schema import parse_result_payload

        result = await CrawlUrl(url="https://example.com", action="invalid")
        payload = parse_result_payload(result)

        assert payload["status"] == "error"
        assert payload["action"] == "invalid"
        assert payload["message"] == "action must be one of: crawl, skeleton, smart"

    @pytest.mark.asyncio
    async def test_crawl_url_normalizes_action_case_and_whitespace(self, monkeypatch):
        """Action normalization should accept padded mixed-case values."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts import crawl_url as crawl_module
        from scripts.crawl_url import CrawlUrl

        from omni.foundation.api.mcp_schema import parse_result_payload

        captured: dict[str, object] = {}

        def _fake_run_skill_command(*, skill_dir, script_name, args):
            captured["args"] = args
            return {"success": True, "content": "ok"}

        monkeypatch.setattr(crawl_module, "run_skill_command", _fake_run_skill_command)
        monkeypatch.setattr(crawl_module, "_generate_chunk_plan", MagicMock(return_value=None))

        result = await CrawlUrl(url="https://example.com", action="  CrAwL  ")
        payload = parse_result_payload(result)

        assert isinstance(payload, dict)
        assert payload.get("success") is True
        args = captured.get("args")
        assert isinstance(args, dict)
        assert args.get("action") == "crawl"


class TestCrawl4aiScriptLoader:
    """Tests for script loading with script_loader."""

    def test_crawl4ai_loads_via_script_loader(self):
        """Test that crawl4ai commands are registered via script_loader."""
        from omni.core.skills.script_loader import ScriptLoader

        skill_path = Path(__file__).parent.parent
        loader = ScriptLoader(skill_path / "scripts", "crawl4ai")
        loader.load_all()

        # Check commands are registered
        assert len(loader.commands) >= 1
        assert "crawl4ai.crawl_url" in loader.commands

    def test_crawl4ai_commands_are_callable(self):
        """Test that registered commands are callable."""
        from omni.core.skills.script_loader import ScriptLoader

        skill_path = Path(__file__).parent.parent
        loader = ScriptLoader(skill_path / "scripts", "crawl4ai")
        loader.load_all()

        crawl_cmd = loader.get_command("crawl4ai.crawl_url")
        assert crawl_cmd is not None
        assert callable(crawl_cmd)

    def test_engine_py_no_skill_command_decorator(self):
        """Test that engine.py does NOT register its own commands.

        This is critical - engine.py should only contain implementation details
        for CLI usage. Commands must come from crawl_url.py to ensure proper
        isolation via run_skill_command.
        """
        skill_path = Path(__file__).parent.parent

        # Import engine module directly
        sys.path.insert(0, str(skill_path))
        import scripts.engine as engine_module

        # engine.py should NOT have @skill_command decorated functions
        # that would override crawl_url.py commands
        for attr_name in dir(engine_module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(engine_module, attr_name)
            if callable(attr) and not attr_name.startswith("_"):
                # Functions in engine.py should NOT be skill commands
                assert not getattr(attr, "_is_skill_command", False), (
                    f"engine.{attr_name} should NOT have @skill_command decorator. "
                    f"Commands must be in crawl_url.py for proper isolation."
                )

    def test_crawl_url_uses_isolation(self):
        """Test that crawl_url command uses run_skill_command (isolation pattern)."""
        import inspect

        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.crawl_url import crawl_url

        # The crawl_url function should call run_skill_command
        # We verify this by checking that crawl_url itself doesn't import crawl4ai
        source = inspect.getsource(crawl_url)
        assert "run_skill_command" in source, (
            "crawl_url should call run_skill_command for isolation"
        )


class TestCrawl4aiIsolation:
    """Tests for isolation pattern."""

    def test_get_skill_dir_returns_correct_path(self):
        """Test that _get_skill_dir returns crawl4ai directory."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.crawl_url import _get_skill_dir

        skill_dir = _get_skill_dir()
        assert skill_dir.name == "crawl4ai"
        assert (skill_dir / "pyproject.toml").exists()
        assert (skill_dir / "scripts").exists()

    def test_run_skill_command_returns_dict(self):
        """Test that run_skill_command returns a dictionary."""
        from omni.foundation.runtime.isolation import run_skill_command

        skill_path = Path(__file__).parent.parent

        # Use a short timeout and mock to avoid actual crawl
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"success": true, "content": "test", "metadata": {}}',
                stderr="",
            )

            result = run_skill_command(
                skill_dir=skill_path,
                script_name="engine.py",
                args={"url": "https://example.com"},
            )

            assert isinstance(result, dict)
            assert "success" in result


class TestCrawl4aiSkillDiscovery:
    """Tests for skill discovery."""

    def test_crawl4ai_not_skipped(self):
        """Test that crawl4ai is not in the skip list."""
        from omni.foundation.config.skills import get_all_skill_paths

        skills = get_all_skill_paths()
        skill_names = [s.name for s in skills]

        assert "crawl4ai" in skill_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
