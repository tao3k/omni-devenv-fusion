"""bindings.py - Core Rust Bindings Isolation Layer.

Safely imports Rust bindings from omni.foundation.
Handles ImportError gracefully without crashing Skills.
"""

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.ext.rust.bindings")


class RustBindings:
    """Manages Rust binding imports for core extensions."""

    _instance = None
    _checked = False
    _available = False
    _error_msg = None

    @classmethod
    def get_instance(cls):
        """Get the Rust bindings instance if available."""
        if not cls._checked:
            cls._try_import()
        return cls._instance

    @classmethod
    def is_available(cls) -> bool:
        """Check if Rust bindings are available."""
        if not cls._checked:
            cls._try_import()
        return cls._available

    @classmethod
    def get_error_message(cls) -> str | None:
        """Get the error message if binding failed."""
        if not cls._checked:
            cls._try_import()
        return cls._error_msg

    @classmethod
    def _try_import(cls):
        """Attempt to import Rust bindings from omni.foundation."""
        cls._checked = True
        try:
            # Import from omni.foundation bridge layer
            # This provides access to Rust implementations
            from omni.foundation.bridge import RustBridge

            cls._instance = RustBridge
            cls._available = True
            logger.debug("Core Rust bindings linked successfully")

        except ImportError as e:
            cls._error_msg = f"Rust bindings not available: {e}"
            logger.debug(f"Rust bindings not available: {e}")
            cls._instance = None
            cls._available = False

        except Exception as e:
            cls._error_msg = f"Unexpected error loading Rust bindings: {e}"
            logger.error(f"Unexpected error loading Rust bindings: {e}")
            cls._instance = None
            cls._available = False


def get_bindings() -> type:
    """Convenience function to get the Rust bindings class."""
    return RustBindings.get_instance()


def is_rust_available() -> bool:
    """Convenience function to check Rust availability."""
    return RustBindings.is_available()
