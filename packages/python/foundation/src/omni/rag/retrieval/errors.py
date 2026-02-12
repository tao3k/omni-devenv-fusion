"""Retrieval-specific exceptions."""

from __future__ import annotations


class HybridRetrievalUnavailableError(RuntimeError):
    """Raised when a backend cannot execute Rust-native hybrid retrieval."""


__all__ = ["HybridRetrievalUnavailableError"]
