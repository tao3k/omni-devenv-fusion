"""Tests for isolation.py - Sidecar Execution Pattern."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest


class TestRunSkillCommand:
    """Tests for run_skill_command function."""

    def test_script_not_found_returns_error(self):
        """Test that missing script returns appropriate error."""
        from omni.foundation.runtime.isolation import run_skill_command

        result = run_skill_command(
            skill_dir=Path("/nonexistent"),
            script_name="engine.py",
            args={"url": "https://example.com"},
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_args_conversion_bool(self):
        """Test that boolean args are converted to 'true'/'false' strings."""
        from omni.foundation.runtime.isolation import run_skill_command

        with TemporaryDirectory() as tmpdir:
            # Create minimal skill structure
            skill_dir = Path(tmpdir)
            (skill_dir / "scripts").mkdir()
            (skill_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n")
            (skill_dir / "scripts" / "engine.py").write_text("# dummy")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout='{"success": true, "content": "", "metadata": {}}',
                    stderr="",
                )

                run_skill_command(
                    skill_dir=skill_dir,
                    script_name="engine.py",
                    args={"fit_markdown": True, "verbose": False},
                )

                # Check that command line args were converted correctly
                mock_run.assert_called_once()
                cmd = mock_run.call_args[1].get("cmd", mock_run.call_args[0][0] if mock_run.call_args[0] else [])
                assert "true" in cmd
                assert "false" in cmd

    def test_args_conversion_string(self):
        """Test that string args are passed correctly."""
        from omni.foundation.runtime.isolation import run_skill_command

        with TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            (skill_dir / "scripts").mkdir()
            (skill_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n")
            (skill_dir / "scripts" / "engine.py").write_text("# dummy")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout='{"success": true, "content": "test", "metadata": {}}',
                    stderr="",
                )

                run_skill_command(
                    skill_dir=skill_dir,
                    script_name="engine.py",
                    args={"url": "https://example.com"},
                )

                mock_run.assert_called_once()
                cmd = mock_run.call_args[1].get("cmd", mock_run.call_args[0][0] if mock_run.call_args[0] else [])
                assert "https://example.com" in cmd


class TestRunSkillCommandAsync:
    """Tests for run_skill_command_async function."""

    def test_async_wrapper_calls_sync_function(self):
        """Test that async wrapper calls the sync function."""
        from omni.foundation.runtime.isolation import run_skill_command_async

        with patch(
            "omni.foundation.runtime.isolation.run_skill_command"
        ) as mock_sync:
            mock_sync.return_value = {"success": True}

            result = run_skill_command_async(
                skill_dir=Path("/tmp"),
                script_name="engine.py",
                args={"url": "https://example.com"},
            )

            mock_sync.assert_called_once()
            assert result["success"] is True


class TestCheckSkillDependencies:
    """Tests for check_skill_dependencies function."""

    def test_missing_pyproject_returns_error(self):
        """Test that missing pyproject.toml returns appropriate error."""
        from omni.foundation.runtime.isolation import check_skill_dependencies

        result = check_skill_dependencies(skill_dir=Path("/nonexistent"))

        assert result["ready"] is False
        assert "no pyproject.toml" in result["error"].lower()

    def test_uv_not_found_returns_error(self):
        """Test that missing uv returns appropriate error."""
        from omni.foundation.runtime.isolation import check_skill_dependencies

        with TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            (skill_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n")

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = FileNotFoundError("uv not found")

                result = check_skill_dependencies(skill_dir=skill_dir)

                assert result["ready"] is False
                assert "uv not found" in result["error"].lower()

    def test_successful_dependency_check(self):
        """Test successful dependency check."""
        from omni.foundation.runtime.isolation import check_skill_dependencies

        with TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            (skill_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

                result = check_skill_dependencies(skill_dir=skill_dir)

                assert result["ready"] is True
                assert result["message"] == "Dependencies satisfied"


class TestJsonParsing:
    """Tests for JSON parsing with and without orjson."""

    def test_json_loads_fallback_to_stdlib(self):
        """Test that parsing falls back to stdlib when orjson unavailable."""
        from omni.foundation.runtime.isolation import _json_loads

        with patch("omni.foundation.runtime.isolation._HAS_ORJSON", False):
            result = _json_loads('{"key": "value"}')
            assert result == {"key": "value"}


class TestIntegration:
    """Integration tests using actual subprocess (slow)."""

    @pytest.mark.slow
    def test_run_skill_command_with_crawl4ai_skill(self):
        """Integration test: run crawl4ai skill via isolation."""
        from omni.foundation.runtime.isolation import run_skill_command

        skill_dir = Path(__file__).parent.parent.parent.parent / "assets" / "skills" / "crawl4ai"

        if not (skill_dir / "pyproject.toml").exists():
            pytest.skip("crawl4ai skill not installed")

        result = run_skill_command(
            skill_dir=skill_dir,
            script_name="engine.py",
            args={"url": "https://example.com", "fit_markdown": True},
            timeout=60,
        )

        # Either succeeds or fails gracefully - should not crash
        assert "success" in result
        # Content may be empty on failure, but should have the key
        assert "content" in result or "error" in result
