"""rust_bridge - Git Skill Rust Extension.

High-performance Git operations using Rust bindings.
Import this package to enable Rust acceleration for the Git skill.

Usage:
    from omni.core.skills.extensions import SkillExtensionLoader

    loader = SkillExtensionLoader("/path/to/git/extensions")
    loader.load_all()

    bridge = loader.get("rust_bridge")
    accelerator = bridge.RustAccelerator("/path/to/repo")
"""

from .accelerator import RustAccelerator, create_accelerator
from .bindings import RustBindings, get_bindings, is_rust_available

__all__ = [
    "RustAccelerator",
    "create_accelerator",
    "RustBindings",
    "get_bindings",
    "is_rust_available",
]
