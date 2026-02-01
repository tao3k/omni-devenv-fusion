# stores/__init__.py
"""
Memory storage implementations.

Provides different storage backends for project memory.

Submodules:
- lancedb: LanceDB-based storage
- file: File-based storage (legacy)
"""

__all__ = []

try:
    from omni.foundation.services.memory.stores.lancedb import LanceDBMemoryStore

    __all__.append("LanceDBMemoryStore")
except ImportError:
    pass

try:
    from omni.foundation.services.memory.stores.file import FileMemoryStore

    __all__.append("FileMemoryStore")
except ImportError:
    pass
