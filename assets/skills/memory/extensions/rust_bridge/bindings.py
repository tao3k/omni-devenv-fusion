"""
bindings.py - Rust Bindings Isolation Layer for Memory Skill

Provides lazy loading of Rust vector store bindings.
"""

import logging

logger = logging.getLogger("omni.skill.memory.rust")


class RustBindings:
    """Lazy loader for Rust bindings."""

    _store_cls = None
    _checked = False

    @classmethod
    def get_store_class(cls):
        """Get the RustVectorStore class if available."""
        if not cls._checked:
            try:
                from omni.foundation.bridge import RustVectorStore

                cls._store_cls = RustVectorStore
                logger.debug("RustVectorStore loaded successfully")
            except ImportError as e:
                cls._store_cls = None
                logger.debug(f"Rust bindings not available: {e}")
            cls._checked = True
        return cls._store_cls

    @classmethod
    def is_available(cls) -> bool:
        """Check if Rust bindings are available."""
        return cls.get_store_class() is not None


__all__ = ["RustBindings"]
