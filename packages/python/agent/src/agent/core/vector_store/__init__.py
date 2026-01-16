# agent/core/vector_store/__init__.py
"""
Vector Memory Store - omni-vector (LanceDB) based RAG for Project Knowledge

Migrated from ChromaDB to omni-vector (Rust + LanceDB)

Provides semantic search over project documentation and code.

Philosophy:
- Fast semantic retrieval for contextual answers
- Persistent storage across sessions
- Auto-ingestion of key knowledge bases

Usage:
    from agent.core.vector_store import get_vector_memory, ingest_knowledge

    # Query the knowledge base
    results = await get_vector_memory().search("git workflow rules", n_results=5)

    # Ingest new knowledge
    await ingest_knowledge(
        documents=[
            "Git workflow requires smart_commit for all commits.",
            "Code reviews must pass before merging."
        ],
        ids=["doc1", "doc2"],
        collection="workflow_rules"
    )
"""

from __future__ import annotations

# Re-export main classes and functions for backward compatibility
from .connection import (
    VectorMemory,
    get_vector_memory,
    SearchResult,
)

# Re-export search operations
from .search import (
    search as search_operation,
    search_knowledge,
    search_knowledge_hybrid,
    search_tools_hybrid,
)

# Re-export ingest operations
from .ingest import (
    add,
    delete,
    count,
    list_collections,
    drop_table,
    ingest_knowledge,
)

# Re-export index operations
from .index import (
    create_index,
    get_tools_by_skill,
    index_skill_tools,
    index_skill_tools_with_schema,
    sync_skills,
)

# Re-export memory operations
from .memory import (
    add_memory,
    search_memory,
)

# Re-export embed operations
from .embed import (
    batch_embed,
    embed_query,
)

# Re-export bootstrap operations
from .bootstrap import (
    bootstrap_knowledge_base,
    ingest_preloaded_skill_definitions,
)

# Also expose methods on VectorMemory class
# These are attached dynamically to maintain the class interface
from . import search as _search_mod
from . import ingest as _ingest_mod
from . import index as _index_mod
from . import memory as _memory_mod

# Attach search methods to VectorMemory
VectorMemory.search = (
    lambda self, query, n_results=5, collection=None, where_filter=None: _search_mod.search(
        self, query, n_results, collection, where_filter
    )
)
VectorMemory.search_tools_hybrid = (
    lambda self, query, keywords=None, limit=15: _search_mod.search_tools_hybrid(
        self, query, keywords, limit
    )
)
VectorMemory.search_knowledge_hybrid = (
    lambda self,
    query,
    keywords=None,
    limit=5,
    table_name="knowledge": _search_mod.search_knowledge_hybrid(
        self, query, keywords, limit, table_name
    )
)

# Attach ingest methods to VectorMemory
VectorMemory.add = lambda self, documents, ids, collection=None, metadatas=None: _ingest_mod.add(
    self, documents, ids, collection, metadatas
)
VectorMemory.delete = lambda self, ids, collection=None: _ingest_mod.delete(self, ids, collection)
VectorMemory.count = lambda self, collection=None: _ingest_mod.count(self, collection)
VectorMemory.list_collections = lambda self: _ingest_mod.list_collections(self)
VectorMemory.drop_table = lambda self, collection=None: _ingest_mod.drop_table(self, collection)

# Attach index methods to VectorMemory
VectorMemory.create_index = lambda self, collection=None: _index_mod.create_index(self, collection)
VectorMemory.get_tools_by_skill = lambda self, skill_name: _index_mod.get_tools_by_skill(
    self, skill_name
)
VectorMemory.index_skill_tools = (
    lambda self, base_path, table_name="skills": _index_mod.index_skill_tools(
        self, base_path, table_name
    )
)
VectorMemory.index_skill_tools_with_schema = (
    lambda self, base_path, table_name="skills": _index_mod.index_skill_tools_with_schema(
        self, base_path, table_name
    )
)
VectorMemory.sync_skills = lambda self, base_path, table_name="skills": _index_mod.sync_skills(
    self, base_path, table_name
)
VectorMemory.export_skill_index = lambda self, output_path=None: _index_mod.export_skill_index(
    self, output_path
)

# Attach memory methods to VectorMemory
VectorMemory.add_memory = lambda self, record: _memory_mod.add_memory(self, record)
VectorMemory.search_memory = lambda self, query, limit=5: _memory_mod.search_memory(
    self, query, limit
)

# Add embedding methods to VectorMemory
VectorMemory._embed_query = lambda self, query: _search_mod.embed_query(query) if query else None
VectorMemory._simple_embed = (
    lambda self, text: _search_mod._simple_embed(text, self.DEFAULT_DIMENSION) if text else None
)
VectorMemory.batch_embed = lambda self, texts: _search_mod.batch_embed(texts)

__all__ = [
    # Main classes
    "VectorMemory",
    "SearchResult",
    # Singleton accessor
    "get_vector_memory",
    # Search operations
    "search_knowledge",
    "search_knowledge_hybrid",
    "search_tools_hybrid",
    # Ingest operations
    "ingest_knowledge",
    # Index operations
    "create_index",
    "get_tools_by_skill",
    "index_skill_tools",
    "index_skill_tools_with_schema",
    "sync_skills",
    # Memory operations
    "add_memory",
    "search_memory",
    # Embed operations
    "batch_embed",
    "embed_query",
    # Bootstrap operations
    "bootstrap_knowledge_base",
    "ingest_preloaded_skill_definitions",
]
