"""Tests for module reuse behavior in tools_loader_script_loading."""

from __future__ import annotations

from typing import TYPE_CHECKING

from omni.core.skills.tools_loader_script_loading import load_script

if TYPE_CHECKING:
    from pathlib import Path


class _NoopLogger:
    def debug(self, *_args, **_kwargs) -> None:
        return


def _write_counter_script(path: Path, *, label: str) -> None:
    path.write_text(
        f"""
import builtins

builtins._omni_tools_loader_script_counter = getattr(
    builtins,
    "_omni_tools_loader_script_counter",
    0,
) + 1

from omni.foundation.api.decorators import skill_command

@skill_command(name="recall", description="{label}")
def recall():
    return "ok"
""".strip(),
        encoding="utf-8",
    )


def _cleanup_skill_modules(skill_name: str) -> None:
    import sys

    prefix = f"{skill_name}."
    for module_name in list(sys.modules.keys()):
        if module_name.startswith(prefix):
            del sys.modules[module_name]


def test_load_script_reuses_module_when_enabled(tmp_path: Path) -> None:
    import builtins

    skill_name = "reuse_skill"
    scripts_path = tmp_path / skill_name / "scripts"
    scripts_path.mkdir(parents=True)
    script_path = scripts_path / "recall.py"
    _write_counter_script(script_path, label="v1")
    _cleanup_skill_modules(skill_name)
    if hasattr(builtins, "_omni_tools_loader_script_counter"):
        delattr(builtins, "_omni_tools_loader_script_counter")

    commands: dict[str, object] = {}
    loaded_count_1, reused_1 = load_script(
        script_path,
        f"{skill_name}.scripts",
        skill_name=skill_name,
        scripts_path=scripts_path,
        context={},
        commands=commands,
        logger=_NoopLogger(),
        allow_module_reuse=True,
    )
    loaded_count_2, reused_2 = load_script(
        script_path,
        f"{skill_name}.scripts",
        skill_name=skill_name,
        scripts_path=scripts_path,
        context={},
        commands=commands,
        logger=_NoopLogger(),
        allow_module_reuse=True,
    )

    assert loaded_count_1 == 1
    assert loaded_count_2 == 1
    assert reused_1 is False
    assert reused_2 is True
    assert builtins._omni_tools_loader_script_counter == 1
    delattr(builtins, "_omni_tools_loader_script_counter")


def test_load_script_reloads_when_file_changes(tmp_path: Path) -> None:
    import builtins
    import time

    skill_name = "reload_skill"
    scripts_path = tmp_path / skill_name / "scripts"
    scripts_path.mkdir(parents=True)
    script_path = scripts_path / "recall.py"
    _write_counter_script(script_path, label="v1")
    _cleanup_skill_modules(skill_name)
    if hasattr(builtins, "_omni_tools_loader_script_counter"):
        delattr(builtins, "_omni_tools_loader_script_counter")

    commands: dict[str, object] = {}
    _ = load_script(
        script_path,
        f"{skill_name}.scripts",
        skill_name=skill_name,
        scripts_path=scripts_path,
        context={},
        commands=commands,
        logger=_NoopLogger(),
        allow_module_reuse=True,
    )

    time.sleep(0.002)
    _write_counter_script(script_path, label="v2")
    _loaded_count_2, reused_2 = load_script(
        script_path,
        f"{skill_name}.scripts",
        skill_name=skill_name,
        scripts_path=scripts_path,
        context={},
        commands=commands,
        logger=_NoopLogger(),
        allow_module_reuse=True,
    )

    assert reused_2 is False
    assert builtins._omni_tools_loader_script_counter == 2
    delattr(builtins, "_omni_tools_loader_script_counter")
