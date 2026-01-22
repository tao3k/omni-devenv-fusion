"""
rust_bridge/__init__.py - Memory Skill Rust Bridge

Exports the NeuralMatrix for use by the Zero-Code Skill Loader.
"""

from .matrix import NeuralMatrix, RustAccelerator
from .bindings import RustBindings

__all__ = ["NeuralMatrix", "RustAccelerator", "RustBindings"]
