"""Skill-command testing utilities to reduce test boilerplate."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from omni.foundation.config.skills import SKILLS_DIR
from omni.foundation.utils import run_async_blocking


class SkillCommandTester:
    """Utility runner for loading and executing skill commands in tests."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir = skills_dir or SKILLS_DIR()
        self._ensure_import_path()

    def _ensure_import_path(self) -> None:
        ensure_skills_import_path(self.skills_dir)

    def load(self, skill: str, module: str, command: str):
        """Load command callable from `<skill>.<module>.<command>`."""
        full_module = f"{skill}.{module}"
        try:
            imported = importlib.import_module(full_module)
        except ModuleNotFoundError:
            # Namespace/package-free fallback: load directly from skill file path.
            module_rel = Path(*module.split(".")).with_suffix(".py")
            module_path = self.skills_dir / skill / module_rel
            if not module_path.exists():
                # Final fallback to repository default skills root.
                from omni.foundation.runtime.gitops import get_project_root

                module_path = get_project_root() / "assets" / "skills" / skill / module_rel
            if not module_path.exists():
                raise

            dynamic_name = f"_omni_skill_{skill}_{module.replace('.', '_')}"
            spec = importlib.util.spec_from_file_location(dynamic_name, module_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load skill module from {module_path}")
            imported = importlib.util.module_from_spec(spec)
            sys.modules[dynamic_name] = imported
            spec.loader.exec_module(imported)
        return getattr(imported, command)

    def run(self, skill: str, module: str, command: str, **kwargs: Any) -> Any:
        """Execute a skill command and resolve async/sync return values.

        Unwraps MCP-style content (content[0].text as JSON) to raw dict for simpler tests.
        """
        func = self.load(skill=skill, module=module, command=command)
        result = func(**kwargs)
        if inspect.isawaitable(result):
            result = run_async_blocking(result)
        return self._unwrap_mcp_content(result)

    @staticmethod
    def _unwrap_mcp_content(result: Any) -> Any:
        """Unwrap MCP content format to raw dict for test assertions."""
        if not isinstance(result, dict):
            return result
        content = result.get("content")
        if not content or not isinstance(content, list) or len(content) == 0:
            return result
        first = content[0]
        if isinstance(first, dict) and first.get("type") == "text":
            text = first.get("text")
            if isinstance(text, str):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass
        return result


@pytest.fixture
def skill_command_tester() -> SkillCommandTester:
    """Fixture exposing SkillCommandTester."""
    return SkillCommandTester()


def ensure_skills_import_path(skills_dir: Path | None = None) -> Path:
    """Ensure skills directory is importable and return resolved path.

    Adds both:
    - active configured skills directory
    - repository default `assets/skills` (stability under test env overrides)
    """
    from omni.foundation.runtime.gitops import get_project_root

    target = skills_dir or SKILLS_DIR()
    candidates = [target, get_project_root() / "assets" / "skills"]
    for candidate in candidates:
        skills_root = str(candidate)
        if skills_root not in sys.path:
            sys.path.insert(0, skills_root)
    return target


__all__ = ["SkillCommandTester", "skill_command_tester", "ensure_skills_import_path"]
