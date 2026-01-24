"""rust_bridge - Core Rust Extension.

Generic Rust accelerator for high-performance operations.
Import this package to enable Rust acceleration for any skill.

Usage:
    from omni.core.skills.extensions import SkillExtensionLoader

    loader = SkillExtensionLoader("/path/to/skill/extensions")
    loader.load_all()

    bridge = loader.get("rust_bridge")
    accelerator = bridge.RustAccelerator("/path/to/repo")
"""

from .accelerator import RustAccelerator, create_accelerator
from .bindings import RustBindings, get_bindings, is_rust_available

__all__ = [
    "RustAccelerator",
    "RustBindings",
    "create_accelerator",
    "get_bindings",
    "is_rust_available",
]
