"""Path and ordering helpers for ToolsLoader."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def prepare_namespace_paths(scripts_path: Path, skill_name: str) -> tuple[list[str], str]:
    """Prepare sys.path for namespace-package script loading."""
    paths_added: list[str] = []
    skill_root = scripts_path.parent
    parent_of_skill = str(skill_root.parent)

    if parent_of_skill not in sys.path:
        sys.path.insert(0, parent_of_skill)
        paths_added.append(parent_of_skill)

    if str(skill_root) not in sys.path:
        sys.path.insert(0, str(skill_root))
        paths_added.append(str(skill_root))

    scripts_path_str = str(scripts_path)
    if scripts_path_str not in sys.path:
        sys.path.insert(0, scripts_path_str)
        paths_added.append(scripts_path_str)

    full_scripts_pkg = f"{skill_name}.scripts"
    return paths_added, full_scripts_pkg


def cleanup_namespace_paths(paths_added: list[str]) -> None:
    """Remove sys.path entries added by prepare_namespace_paths()."""
    for path in paths_added:
        if path in sys.path:
            sys.path.remove(path)


def iter_script_files(scripts_path: Path) -> list[Path]:
    """Return all script files in deterministic dependency-friendly order."""
    all_files: list[Path] = []
    for py_file in scripts_path.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        all_files.append(py_file)

    non_underscore_files = [f for f in all_files if not f.stem.startswith("_")]
    underscore_files = [f for f in all_files if f.stem.startswith("_")]

    def depth_then_name(p: Path) -> tuple[int, str]:
        return (len(p.relative_to(scripts_path).parts), str(p))

    non_underscore_files.sort(key=depth_then_name)
    underscore_files.sort(key=depth_then_name)
    return non_underscore_files + underscore_files


def scripts_pkg_for_file(py_file: Path, scripts_path: Path, full_scripts_pkg: str) -> str:
    """Compute scripts package path for one file."""
    rel_path = py_file.relative_to(scripts_path)
    pkg_parts = list(rel_path.parent.parts)
    pkg_suffix = ".".join(pkg_parts)
    return f"{full_scripts_pkg}.{pkg_suffix}" if pkg_suffix else full_scripts_pkg
