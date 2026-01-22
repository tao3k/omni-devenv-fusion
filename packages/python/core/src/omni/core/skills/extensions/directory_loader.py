"""
directory_loader.py - Directory Extension Loader

Loads extensions from directory, supporting:
- Directory packages (rust_bridge/__init__.py)
- Single-file modules (hooks.py)

Usage:
    from omni.core.skills.extensions import DirectoryExtensionLoader

    loader = DirectoryExtensionLoader()
    extensions = loader.load(skill_path, context)
"""

from __future__ import annotations

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.skills.extensions.directory")


class DirectoryExtensionLoader:
    """Load extensions from directory."""

    def load(self, skill_path: Path, context: dict[str, Any]) -> list[ISkillExtension]:
        """Load all extensions from directory."""
        ext_path = skill_path / "extensions"
        if not ext_path.exists():
            return []

        extensions: list[ISkillExtension] = []

        for item in ext_path.iterdir():
            if item.name.startswith("_"):
                continue

            if item.is_dir() and (item / "__init__.py").exists():
                # Directory package
                ext = self._load_package(item, context)
                if ext:
                    extensions.append(ext)

            elif item.is_file() and item.suffix == ".py":
                # Single-file module
                ext = self._load_file(item, context)
                if ext:
                    extensions.append(ext)

        return extensions

    def _load_package(self, path: Path, context: dict[str, Any]) -> ISkillExtension | None:
        """Load a directory package."""
        try:
            init_file = path / "__init__.py"
            # Create package spec, set submodule_search_locations
            spec = importlib.util.spec_from_file_location(
                path.name,
                init_file,
                submodule_search_locations=[str(path)],
            )
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            extension = self._instantiate_extension(module, path.name, context)
            if extension:
                logger.info(f"Loaded package extension: {path.name}")

            return extension

        except Exception as e:
            logger.error(f"Failed to load package '{path.name}': {e}")
            return None

    def _load_file(self, path: Path, context: dict[str, Any]) -> ISkillExtension | None:
        """Load a single-file module."""
        try:
            module_name = path.stem
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            extension = self._instantiate_extension(module, module_name, context)
            if extension:
                logger.info(f"Loaded script extension: {module_name}")

            return extension

        except Exception as e:
            logger.error(f"Failed to load script '{path.stem}': {e}")
            return None

    def _instantiate_extension(
        self, module: Any, module_name: str, context: dict[str, Any]
    ) -> ISkillExtension | None:
        """Instantiate extension object."""
        # Method 1: Factory function create()
        if hasattr(module, "create"):
            try:
                return module.create(context)
            except Exception as e:
                logger.error(f"create() failed for {module_name}: {e}")
                return None

        # Method 2: Class named Extension
        if hasattr(module, "Extension"):
            try:
                return module.Extension(context)
            except Exception as e:
                logger.error(f"Extension class failed for {module_name}: {e}")
                return None

        # Method 3: If module itself is an ISkillExtension instance
        if isinstance(module, ISkillExtension):
            return module

        logger.debug(f"No extension found in {module_name}")
        return None


__all__ = ["DirectoryExtensionLoader"]
