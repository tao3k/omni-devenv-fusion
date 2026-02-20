"""Variant discovery/loading orchestration for ToolsLoader."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .tools_loader_script_loading import load_variant_script

if TYPE_CHECKING:
    from pathlib import Path


def load_variants(
    *,
    scripts_path: Path,
    scripts_pkg: str,
    skill_name: str,
    variants_dir: str,
    context: dict[str, Any],
    variant_commands: dict[str, dict[str, Any]],
    logger: Any,
) -> None:
    """Load variant implementations from variants/ directory."""
    variants_path = scripts_path / variants_dir
    if not variants_path.exists():
        logger.debug(f"[{skill_name}] No variants directory found: {variants_path}")
        return

    for command_dir in variants_path.iterdir():
        if not command_dir.is_dir():
            continue
        command_name = command_dir.name
        if command_name.startswith("_"):
            continue

        for variant_file in command_dir.glob("*.py"):
            if variant_file.stem.startswith("_"):
                continue
            variant_name = variant_file.stem
            try:
                load_variant_script(
                    variant_file,
                    scripts_pkg,
                    skill_name=skill_name,
                    variants_dir=variants_dir,
                    context=context,
                    variant_commands=variant_commands,
                    command_name=command_name,
                    variant_name=variant_name,
                    logger=logger,
                )
            except Exception as e:
                logger.debug(
                    f"[{skill_name}] Failed to load variant {command_name}/{variant_name}: {e}"
                )

    logger.debug(f"[{skill_name}] Loaded {sum(len(v) for v in variant_commands.values())} variants")
