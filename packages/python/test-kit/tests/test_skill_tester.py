"""Tests for SkillCommandTester utility."""

from __future__ import annotations

import asyncio
from pathlib import Path

from omni.test_kit.skill import SkillCommandTester, ensure_skills_import_path


def test_skill_command_tester_loads_command() -> None:
    tester = SkillCommandTester()
    command = tester.load("demo", "scripts.commands", "echo")
    assert callable(command)


def test_skill_command_tester_runs_async_command() -> None:
    tester = SkillCommandTester()
    result = tester.run("demo", "scripts.commands", "echo", message="hello")
    assert result["original_message"] == "hello"
    assert result["echoed_message"] == "Echo: hello"


def test_skill_command_tester_runs_async_command_inside_event_loop() -> None:
    tester = SkillCommandTester()

    async def _run() -> dict:
        return tester.run("demo", "scripts.commands", "echo", message="inside-loop")

    result = asyncio.run(_run())
    assert result["original_message"] == "inside-loop"
    assert result["echoed_message"] == "Echo: inside-loop"


def test_ensure_skills_import_path_returns_path() -> None:
    target = ensure_skills_import_path()
    assert target.exists()


def test_skill_command_tester_uses_repo_fallback_skills_path(monkeypatch, tmp_path) -> None:
    """Should still load repo demo skill when PRJ_CONFIG_HOME points elsewhere."""
    empty_conf = tmp_path / "empty_conf"
    empty_conf.mkdir(parents=True)
    monkeypatch.setenv("PRJ_CONFIG_HOME", str(empty_conf))

    from omni.foundation.config.dirs import PRJ_DIRS

    PRJ_DIRS.clear_cache()

    tester = SkillCommandTester()
    command = tester.load("demo", "scripts.commands", "echo")
    assert callable(command)
    # Ensure we loaded the repo skill module, not a temp path.
    assert (
        Path(command.__code__.co_filename)
        .as_posix()
        .endswith("assets/skills/demo/scripts/commands.py")
    )
