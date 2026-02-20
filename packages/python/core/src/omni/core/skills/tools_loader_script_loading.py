"""Script/variant module loading helpers for ToolsLoader."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def load_script(
    path: Path,
    scripts_pkg: str,
    *,
    skill_name: str,
    scripts_path: Path,
    context: dict[str, Any],
    commands: dict[str, Any],
    logger: Any,
    allow_module_reuse: bool = False,
) -> tuple[int, bool]:
    """Load one script module and harvest @skill_command handlers."""
    import importlib.util
    import types

    module_name = path.stem
    full_module_name = f"{scripts_pkg}.{module_name}"
    stat = path.stat()
    current_mtime_ns = stat.st_mtime_ns
    current_size = stat.st_size
    reused = False

    try:
        parts = full_module_name.split(".")
        scripts_path_str = str(scripts_path)

        for i in range(1, len(parts)):
            parent_pkg = ".".join(parts[:i])
            parent_parts = parts[2:i]
            if parent_parts:
                parent_path = scripts_path_str
                for part in parent_parts:
                    parent_path = str(Path(parent_path) / part)
            else:
                parent_path = scripts_path_str

            if parent_pkg not in sys.modules:
                m = types.ModuleType(parent_pkg)
                m.__path__ = [parent_path]
                sys.modules[parent_pkg] = m
            else:
                parent_mod = sys.modules[parent_pkg]
                if hasattr(parent_mod, "__path__") and parent_path not in parent_mod.__path__:
                    parent_mod.__path__.append(parent_path)

        module = None
        existing_module = sys.modules.get(full_module_name)
        if (
            allow_module_reuse
            and existing_module is not None
            and str(getattr(existing_module, "__file__", "")) == str(path)
            and getattr(existing_module, "__omni_mtime_ns__", None) == current_mtime_ns
            and getattr(existing_module, "__omni_size__", None) == current_size
        ):
            module = existing_module
            reused = True
            for key, value in context.items():
                setattr(module, key, value)
            module.skill_name = skill_name
        else:
            spec = importlib.util.spec_from_file_location(full_module_name, path)
            if not (spec and spec.loader):
                return 0, False

            module = importlib.util.module_from_spec(spec)
            module.__package__ = ".".join(parts[:-1])

            script_dir = str(path.parent)
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)

            sys.modules[full_module_name] = module

            for key, value in context.items():
                setattr(module, key, value)
            module.skill_name = skill_name

            spec.loader.exec_module(module)
            module.__omni_mtime_ns__ = current_mtime_ns
            module.__omni_size__ = current_size

        count = 0
        last_full_name: str | None = None
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)

            if hasattr(attr, "_is_skill_command") and attr._is_skill_command:
                config = getattr(attr, "_skill_config", {})
                cmd_name = (
                    config.get("name") if config else getattr(attr, "_command_name", attr_name)
                )
                full_name = f"{skill_name}.{cmd_name}"
                commands[full_name] = attr
                last_full_name = full_name
                count += 1

        if count > 0 and last_full_name is not None:
            logger.debug(f"[{skill_name}] Modular load success: {last_full_name}")
        return count, reused

    except Exception as e:
        logger.debug(f"[{skill_name}] Modular load failed for {path}: {e}")
        if full_module_name in sys.modules and not reused:
            del sys.modules[full_module_name]
        return 0, False


def load_variant_script(
    path: Path,
    scripts_pkg: str,
    *,
    skill_name: str,
    variants_dir: str,
    context: dict[str, Any],
    variant_commands: dict[str, dict[str, Any]],
    command_name: str,
    variant_name: str,
    logger: Any,
) -> None:
    """Load one variant module and harvest variant handlers."""
    import importlib.util
    import types

    full_module_name = f"{scripts_pkg}.{variants_dir}.{path.parent.name}.{path.stem}"

    try:
        parent_pkg = f"{scripts_pkg}.{variants_dir}.{path.parent.name}"
        if parent_pkg not in sys.modules:
            m = types.ModuleType(parent_pkg)
            m.__path__ = [str(path.parent)]
            sys.modules[parent_pkg] = m

        spec = importlib.util.spec_from_file_location(full_module_name, path)
        if not (spec and spec.loader):
            return

        module = importlib.util.module_from_spec(spec)
        module.__package__ = scripts_pkg

        for key, value in context.items():
            setattr(module, key, value)
        module.skill_name = skill_name

        sys.modules[full_module_name] = module
        spec.loader.exec_module(module)

        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)

            if hasattr(attr, "_is_skill_command") and attr._is_skill_command:
                config = getattr(attr, "_skill_config", {})
                config["variant"] = variant_name
                config["variant_source"] = str(path)
                variant_commands.setdefault(command_name, {})[variant_name] = attr
                logger.debug(f"[{skill_name}] Loaded variant: {command_name}/{variant_name}")

    except Exception as e:
        logger.debug(f"[{skill_name}] Failed to load variant script {path}: {e}")
        if full_module_name in sys.modules:
            del sys.modules[full_module_name]
