"""
Fake Implementations for Testing.

This package provides protocol-compliant fake implementations for testing
without external dependencies (databases, APIs, file systems, etc.).

Usage:
    from tests.fakes import FakeVectorStore, FakeMCP, FakeInference

    def test_feature(fake_registry):
        store = FakeVectorStore()
        ...
"""

from .fake_inference import FakeInference
from .fake_mcp_server import FakeMCPServer
from .fake_registry import FakeSkillRegistry
from .fake_vectorstore import FakeVectorStore

__all__ = [
    "FakeVectorStore",
    "FakeMCPServer",
    "FakeInference",
    "FakeSkillRegistry",
]
