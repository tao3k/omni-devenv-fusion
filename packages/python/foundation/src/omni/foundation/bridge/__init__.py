"""
Bridge Module - Rust Bindings Isolation Layer

This module provides a clean interface between Python and Rust bindings.
Only this module should contain `import omni_rust_bindings` calls.

Architecture:
- types.py: Python-side data structures (dataclasses)
- interfaces.py: Protocol definitions (ABC/Protocol)
- rust_*.py: Rust binding implementations (split for modularity)

Modules:
- rust_vector.py: Vector store (LanceDB)
- rust_analyzer.py: Code analysis (ast-grep)
- rust_scanner.py: Skill scanner (skills-scanner)

Usage:
    from omni.foundation.bridge import RustVectorStore, SearchResult
    from omni.foundation.bridge.interfaces import VectorStoreProvider
"""

from __future__ import annotations

from typing import Any

# Lazy exports - avoid importing at module level to prevent recursion
_lazy_types = None
_lazy_interfaces = None


def __getattr__(name: str):
    """Lazy load bridge submodules."""
    global _lazy_types, _lazy_interfaces

    # Types
    if name in (
        "SearchResult",
        "FileContent",
        "VectorMetadata",
        "CodeSymbol",
        "ScanResult",
        "SkillStructure",
        "IngestResult",
    ):
        if _lazy_types is None:
            from . import types

            _lazy_types = types
        return getattr(_lazy_types, name)

    # Interfaces
    if name in (
        "VectorStoreProvider",
        "CodeAnalysisProvider",
        "FileScannerProvider",
        "SkillScannerProvider",
    ):
        if _lazy_interfaces is None:
            from . import interfaces

            _lazy_interfaces = interfaces
        return getattr(_lazy_interfaces, name)

    # Implementations - import from new modular files
    if name in (
        "RustVectorStore",
        "get_vector_store",
        "RUST_AVAILABLE",
    ):
        from .rust_vector import RUST_AVAILABLE, RustVectorStore, get_vector_store

        return (
            RustVectorStore
            if name == "RustVectorStore"
            else (get_vector_store if name == "get_vector_store" else RUST_AVAILABLE)
        )

    if name in ("ToolRecordValidationError", "validate_tool_record", "validate_tool_records"):
        from .tool_record_validation import (
            ToolRecordValidationError,
            validate_tool_record,
            validate_tool_records,
        )

        return (
            ToolRecordValidationError
            if name == "ToolRecordValidationError"
            else (validate_tool_record if name == "validate_tool_record" else validate_tool_records)
        )

    if name in (
        "RustCodeAnalyzer",
        "get_code_analyzer",
    ):
        from .rust_analyzer import RustCodeAnalyzer, get_code_analyzer

        return RustCodeAnalyzer if name == "RustCodeAnalyzer" else get_code_analyzer

    if name in ("RustSkillScanner",):
        from .rust_scanner import RustSkillScanner

        return RustSkillScanner

    # Immune System Bridge
    if name == "rust_immune":
        from . import rust_immune

        return rust_immune

    # Status functions
    if name in (
        "is_rust_available",
        "check_rust_availability",
    ):
        # Re-export from scanner (same check applies to all)
        from .rust_scanner import RUST_AVAILABLE

        def is_rust_available() -> bool:
            return RUST_AVAILABLE

        def check_rust_availability() -> dict[str, Any]:
            return {
                "available": RUST_AVAILABLE,
                "message": "Rust bindings loaded successfully"
                if RUST_AVAILABLE
                else "Rust bindings not available - using pure Python fallbacks",
            }

        return is_rust_available if name == "is_rust_available" else check_rust_availability

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """List available attributes for autocomplete."""
    return [
        # Validation
        "ToolRecordValidationError",
        "validate_tool_record",
        "validate_tool_records",
        # Types
        "SearchResult",
        "FileContent",
        "VectorMetadata",
        "CodeSymbol",
        "ScanResult",
        "SkillStructure",
        "IngestResult",
        # Interfaces
        "VectorStoreProvider",
        "CodeAnalysisProvider",
        "FileScannerProvider",
        "SkillScannerProvider",
        # Implementations
        "RustVectorStore",
        "RustCodeAnalyzer",
        "RustSkillScanner",
        "rust_immune",
        # Factories
        "get_vector_store",
        "get_code_analyzer",
        # Status
        "RUST_AVAILABLE",
        "is_rust_available",
        "check_rust_availability",
    ]
