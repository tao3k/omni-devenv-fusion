"""
rust_bridge/__init__.py - Memory Skill Rust Bridge

Exports the NeuralMatrix for use by the Zero-Code Skill Loader.
"""

from .bindings import RustBindings
from .matrix import NeuralMatrix, RustAccelerator

__all__ = ["NeuralMatrix", "RustAccelerator", "RustBindings"]
