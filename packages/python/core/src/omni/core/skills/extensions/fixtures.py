"""
fixtures.py - Extension Fixture System

Injects extension functionality into functions in scripts.

Architecture:
    scripts/status.py           <-- Defines WHAT (decorated with @skill_command)
        def git_status(): ...

    extensions/rust_bridge/     <-- Provides HOW (Rust implementation)
        def rust_status(): ...

    fixtures.py                 <-- Bridge: injects Rust into Python
        fixture("rust_bridge", "git_status", rust_status)

Usage:
    # Called during skill initialization
    from omni.core.skills.extensions.fixtures import FixtureManager
    manager = FixtureManager(skill_path)
    manager.apply_fixtures_to_module(scripts_module)
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.skills.fixtures")


class FixtureRegistry:
    """Global extension fixture registry."""

    _registry: dict[str, dict[str, Callable]] = {}

    @classmethod
    def register(cls, ext_name: str, func_name: str, impl: Callable) -> None:
        """Register a fixture implementation."""
        if ext_name not in cls._registry:
            cls._registry[ext_name] = {}
        cls._registry[ext_name][func_name] = impl
        logger.debug(f"Registered fixture: {ext_name}.{func_name}")

    @classmethod
    def get(cls, ext_name: str, func_name: str) -> Callable | None:
        """Get fixture implementation."""
        return cls._registry.get(ext_name, {}).get(func_name)

    @classmethod
    def clear(cls, ext_name: str | None = None) -> None:
        """Clear the registry."""
        if ext_name:
            cls._registry.pop(ext_name, None)
        else:
            cls._registry.clear()

    @classmethod
    def list_registered(cls) -> dict[str, list[str]]:
        """List all registered fixtures."""
        return {k: list(v.keys()) for k, v in cls._registry.items()}


class FixtureManager:
    """Load and apply fixtures from extensions directory."""

    def __init__(self, skill_path: Path):
        self.skill_path = skill_path
        self.ext_path = skill_path / "extensions"

    def discover_and_register(self) -> dict[str, list[str]]:
        """Discover all extensions and register their fixtures."""
        fixtures_found: dict[str, list[str]] = {}

        if not self.ext_path.exists():
            logger.debug(f"No extensions directory: {self.ext_path}")
            return fixtures_found

        for item in self.ext_path.iterdir():
            if item.name.startswith("_"):
                continue

            if item.is_dir() and (item / "__init__.py").exists():
                ext_name = item.name
                registered = self._load_extension_fixtures(item, ext_name)
                if registered:
                    fixtures_found[ext_name] = registered

        return fixtures_found

    def _load_extension_fixtures(self, ext_path: Path, ext_name: str) -> list[str]:
        """Load fixtures from a single extension."""
        try:
            init_file = ext_path / "__init__.py"
            spec = importlib.util.spec_from_file_location(
                ext_name, init_file, submodule_search_locations=[str(ext_path)]
            )
            if spec is None or spec.loader is None:
                return []

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Look for the extension's fixtures list
            fixtures = getattr(module, "FIXTURES", {})
            registered = []

            for func_name, impl in fixtures.items():
                FixtureRegistry.register(ext_name, func_name, impl)
                registered.append(func_name)
                logger.info(f"Fixture loaded: {ext_name}.{func_name}")

            return registered

        except Exception as e:
            logger.error(f"Failed to load fixtures from {ext_name}: {e}")
            return []

    def apply_fixtures_to_module(self, module: Any) -> None:
        """Apply registered fixtures to module functions."""
        # First discover and load fixtures
        self.discover_and_register()

        # Iterate over functions marked as needing fixtures
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue

            attr = getattr(module, attr_name)
            if not callable(attr):
                continue

            # Check for fixture metadata
            fixture_info = getattr(attr, "_fixture_info", None)
            if fixture_info is None:
                continue

            ext_name, func_name = fixture_info
            impl = FixtureRegistry.get(ext_name, func_name)

            if impl:
                # Replace original function with extension implementation
                setattr(module, attr_name, impl)
                logger.debug(f"Applied fixture: {ext_name}.{func_name} -> {attr_name}")


def fixture(ext_name: str, func_name: str):
    """Decorator: mark function to be replaced by fixture.

    Usage:
        # In scripts/status.py
        @skill_command
        @fixture("rust_bridge", "git_status")
        def git_status(ctx):
            # Python implementation (used if Rust is not available)
            ...
    """

    def decorator(func: Callable) -> Callable:
        func._fixture_info = (ext_name, func_name)
        return func

    return decorator


def apply_fixtures(skill_path: Path, module: Any) -> None:
    """Convenience function: apply all fixtures to a module."""
    manager = FixtureManager(skill_path)
    manager.apply_fixtures_to_module(module)


__all__ = [
    "FixtureManager",
    "FixtureRegistry",
    "apply_fixtures",
    "fixture",
]
