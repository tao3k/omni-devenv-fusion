"""Tests for Rust-scanner command index cache in tools_loader_index."""

from __future__ import annotations

from typing import TYPE_CHECKING

from omni.core.skills.tools_loader_index import build_rust_command_index

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _write_skill_script(scripts_dir: Path, filename: str, content: str) -> Path:
    path = scripts_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def _fake_tool_record(skill_name: str, tool_name: str, file_path: Path):
    class _Tool:
        def __init__(self):
            self.tool_name = tool_name
            self.file_path = str(file_path)
            self.description = "desc"
            self.skill_name = skill_name
            self.function_name = tool_name.split(".")[-1]
            self.execution_mode = "sync"
            self.keywords = []
            self.input_schema = "{}"
            self.docstring = ""
            self.file_hash = "abc123"
            self.category = "search"

    return _Tool()


def test_build_rust_command_index_uses_cache_across_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill_name = "cache_skill"
    skill_root = tmp_path / skill_name
    scripts_dir = skill_root / "scripts"
    scripts_dir.mkdir(parents=True)
    recall_path = _write_skill_script(
        scripts_dir,
        "recall.py",
        """
from omni.foundation.api.decorators import skill_command

@skill_command(name="recall", description="Recall")
def recall():
    return "ok"
""".strip(),
    )

    calls = {"count": 0}
    tool = _fake_tool_record(skill_name, f"{skill_name}.recall", recall_path)

    class _Scanner:
        def __init__(self, _base_path: str):
            calls["count"] += 1

        def scan_skill_with_tools(self, _target_skill: str):
            return (object(), [tool])

    import omni_core_rs

    monkeypatch.setattr(omni_core_rs, "PySkillScanner", _Scanner)

    idx1 = build_rust_command_index(skill_name, scripts_dir)
    idx2 = build_rust_command_index(skill_name, scripts_dir)

    assert calls["count"] == 1
    assert "recall" in idx1
    assert idx1 == idx2


def test_build_rust_command_index_invalidates_cache_on_script_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill_name = "cache_skill_mutate"
    skill_root = tmp_path / skill_name
    scripts_dir = skill_root / "scripts"
    scripts_dir.mkdir(parents=True)
    recall_path = _write_skill_script(
        scripts_dir,
        "recall.py",
        """
from omni.foundation.api.decorators import skill_command

@skill_command(name="recall", description="Recall")
def recall():
    return "ok"
""".strip(),
    )

    calls = {"count": 0}
    tool = _fake_tool_record(skill_name, f"{skill_name}.recall", recall_path)

    class _Scanner:
        def __init__(self, _base_path: str):
            calls["count"] += 1

        def scan_skill_with_tools(self, _target_skill: str):
            return (object(), [tool])

    import omni_core_rs

    monkeypatch.setattr(omni_core_rs, "PySkillScanner", _Scanner)

    idx1 = build_rust_command_index(skill_name, scripts_dir)
    recall_path.write_text(
        """
from omni.foundation.api.decorators import skill_command

@skill_command(name="recall", description="Recall v2")
def recall():
    return "ok-v2"
""".strip(),
        encoding="utf-8",
    )
    idx2 = build_rust_command_index(skill_name, scripts_dir)

    assert calls["count"] == 2
    assert "recall" in idx1
    assert "recall" in idx2
