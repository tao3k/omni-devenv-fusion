"""
rust_impl.py - Legacy Rust Bindings Wrapper (Deprecated)

This module provides backward compatibility wrappers for the Rust bindings.
New code should use the modular imports:
- from omni.foundation.bridge.rust_vector import RustVectorStore
- from omni.foundation.bridge.rust_analyzer import RustCodeAnalyzer
- from omni.foundation.bridge.rust_scanner import RustSkillScanner

This module re-exports from the new modular files for backward compatibility.
"""

from __future__ import annotations

import os
from typing import Any

from omni.foundation.config.logging import get_logger

# Note: omni_rust_bindings import moved to modular files
# This file re-exports from them for backward compatibility
RUST_AVAILABLE = False

from .interfaces import FileScannerProvider

logger = get_logger("omni.bridge.rust")

# =============================================================================
# Re-export from modular implementations (for backward compatibility)
# =============================================================================

# Vector Store
from .rust_vector import RustVectorStore
from .rust_vector import get_vector_store as _get_vector_store


def get_vector_store(index_path: str = "data/vector.db", dimension: int = 1536) -> RustVectorStore:
    """Get or create the global vector store instance."""
    return _get_vector_store(index_path, dimension)


# Code Analyzer
from .rust_analyzer import RustCodeAnalyzer
from .rust_analyzer import get_code_analyzer as _get_code_analyzer


def get_code_analyzer() -> RustCodeAnalyzer:
    """Get the global code analyzer instance."""
    return _get_code_analyzer()


# Skill Scanner
from .rust_scanner import RustSkillScanner

# =============================================================================
# Status Functions
# =============================================================================


def is_rust_available() -> bool:
    """Check if Rust bindings are available."""
    return RUST_AVAILABLE


def check_rust_availability() -> dict[str, Any]:
    """Check Rust bindings availability and return status info."""
    return {
        "available": RUST_AVAILABLE,
        "message": "Rust bindings loaded successfully"
        if RUST_AVAILABLE
        else "Rust bindings not available - using pure Python fallbacks",
    }


# =============================================================================
# Legacy: File Scanner (not yet modularized)
# =============================================================================


class RustFileScanner(FileScannerProvider):
    """File scanner implementation using Rust bindings."""

    def __init__(self):
        logger.info("Initialized RustFileScanner")

    def scan_directory(
        self,
        path: str,
        pattern: str | None = None,
        max_depth: int | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[str]:
        """Scan a directory and return matching file paths."""
        results = []
        for root, dirs, files in os.walk(path):
            if max_depth:
                depth = root.replace(path, "").count(os.sep)
                if depth >= max_depth:
                    dirs.clear()
                    continue
            for f in files:
                if pattern and pattern not in f:
                    continue
                results.append(os.path.join(root, f))
        return results

    def get_file_info(self, path: str) -> dict[str, Any] | None:
        """Get metadata about a file."""
        if not os.path.exists(path):
            return None
        stat = os.stat(path)
        return {
            "path": path,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "is_file": os.path.isfile(path),
            "is_dir": os.path.isdir(path),
        }

    def is_safe_path(self, base_path: str, target_path: str) -> bool:
        """Check if a target path is within the base path."""
        base = os.path.abspath(base_path)
        target = os.path.abspath(target_path)
        return target.startswith(base + os.sep)


# =============================================================================
# Legacy: RustBridge (deprecated)
# =============================================================================


class RustBridge:
    """Legacy wrapper for backward compatibility.

    DEPRECATED: Use the provider classes directly.
    """

    def __init__(self):
        import warnings

        warnings.warn(
            "RustBridge is deprecated, use RustVectorStore, RustCodeAnalyzer directly",
            DeprecationWarning,
        )
        self.vector = get_vector_store()
        self.analyzer = get_code_analyzer()
        self.scanner = RustSkillScanner()

    @property
    def is_available(self) -> bool:
        return RUST_AVAILABLE


__all__ = [
    # Re-exports from modular implementations
    "RustVectorStore",
    "RustCodeAnalyzer",
    "RustSkillScanner",
    # Factories
    "get_vector_store",
    "get_code_analyzer",
    # Status
    "RUST_AVAILABLE",
    "is_rust_available",
    "check_rust_availability",
    # Legacy (not yet modularized)
    "RustFileScanner",
    # Legacy wrapper
    "RustBridge",
]
