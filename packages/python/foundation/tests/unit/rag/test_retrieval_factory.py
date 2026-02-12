"""Tests for retrieval backend factory."""

from __future__ import annotations

import pytest

from omni.rag import (
    LanceRetrievalBackend,
    HybridRetrievalBackend,
    create_retrieval_backend,
)


def test_factory_creates_lance_backend():
    backend = create_retrieval_backend("lance")
    assert isinstance(backend, LanceRetrievalBackend)


def test_factory_creates_hybrid_backend():
    backend = create_retrieval_backend("hybrid")
    assert isinstance(backend, HybridRetrievalBackend)


def test_factory_creates_rust_owned_hybrid_backend():
    backend = create_retrieval_backend("hybrid")
    assert isinstance(backend, HybridRetrievalBackend)


def test_factory_rejects_unknown_kind():
    with pytest.raises(ValueError):
        create_retrieval_backend("unknown")


def test_factory_rejects_legacy_aliases():
    with pytest.raises(ValueError):
        create_retrieval_backend("lancedb")
    with pytest.raises(ValueError):
        create_retrieval_backend("vector")
