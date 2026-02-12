"""Skill execution fixtures and helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from omni.core.kernel.components.skill_loader import load_skill_scripts
from omni.foundation.config.skills import SKILLS_DIR


@dataclass
class SkillResult:
    """Represents the result of a skill execution."""

    success: bool
    output: Any
    error: str | None = None
    artifacts: dict | None = None


class SkillTester:
    """Dedicated Skill Test Executor."""

    def __init__(self, request):
        self.request = request
        self.context = MagicMock()
        self.config = {}
        self.skills_root = SKILLS_DIR()

    def with_config(self, config: dict[str, Any]) -> "SkillTester":
        self.config.update(config)
        return self

    def with_context(self, **kwargs) -> "SkillTester":
        for key, value in kwargs.items():
            setattr(self.context, key, value)
        return self

    async def run(self, _skill_name: str, _command_name: str, **kwargs) -> SkillResult:
        """Execute the core logic of a Skill."""
        scripts_dir = self.skills_root / _skill_name / "scripts"
        commands = await load_skill_scripts(_skill_name, scripts_dir)

        if _command_name not in commands:
            return SkillResult(
                success=False, output=None, error=f"Command '{_command_name}' not found"
            )

        func = commands[_command_name]
        try:
            if asyncio.iscoroutinefunction(func):
                output = await func(**kwargs)
            else:
                output = func(**kwargs)
            return SkillResult(success=True, output=output)
        except Exception as exc:
            return SkillResult(success=False, output=None, error=str(exc))

    async def get_commands(self, skill_name: str) -> dict[str, Any]:
        """Get all available commands for a skill."""
        scripts_dir = self.skills_root / skill_name / "scripts"
        return await load_skill_scripts(skill_name, scripts_dir)


@pytest.fixture
async def skill_tester(request):
    return SkillTester(request)


__all__ = ["SkillResult", "SkillTester", "skill_tester"]
