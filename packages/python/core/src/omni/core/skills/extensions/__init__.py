"""extensions - Extension Loader Subsystem.

Provides dynamic extension loading for skills with support for:
- Single-file extensions (hooks.py)
- Package extensions (rust_bridge/__init__.py)
- Lazy loading and dependency management

Usage:
    from omni.core.skills.extensions import SkillExtensionLoader, ExtensionWrapper

    loader = SkillExtensionLoader("/path/to/extensions")
    loader.load_all()

    # Get extension
    ext = loader.get("rust_bridge")
    if ext:
        ext.initialize(context)
"""

from .loader import SkillExtensionLoader, get_extension_loader
from .wrapper import ExtensionWrapper

__all__ = [
    "SkillExtensionLoader",
    "get_extension_loader",
    "ExtensionWrapper",
]
