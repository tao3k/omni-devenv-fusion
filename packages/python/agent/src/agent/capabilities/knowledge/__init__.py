# capabilities/knowledge
"""
Knowledge Management Module

Phase 32: Modularized subpackage.

Modules:
- ingestor.py: Knowledge ingestion from files and repomix XML
- librarian.py: RAG-powered knowledge base queries

Usage:
    # New modular imports (recommended)
    from agent.capabilities.knowledge.ingestor import ingest_all_knowledge
    from agent.capabilities.knowledge.librarian import consult_knowledge_base

    # Old imports (still work for backward compatibility)
    from agent.capabilities.knowledge import consult_knowledge_base
    from agent.capabilities.knowledge import ingest_all_knowledge
"""

from .ingestor import (
    REPOMIX_XML_PATH,
    DEFAULT_KNOWLEDGE_DIRS,
    get_knowledge_dirs,
    extract_keywords,
    ingest_file,
    ingest_directory,
    ingest_all_knowledge,
    ingest_thread_specific_knowledge,
    ingest_git_workflow_knowledge,
    ingest_from_repomix_xml,
    main,
)

from .librarian import (
    consult_knowledge_base,
    ingest_knowledge,
    bootstrap_knowledge,
    list_knowledge_domains,
    search_project_rules,
)

# Backward compatibility: Re-export everything
__all__ = [
    # From ingestor
    "REPOMIX_XML_PATH",
    "DEFAULT_KNOWLEDGE_DIRS",
    "get_knowledge_dirs",
    "extract_keywords",
    "ingest_file",
    "ingest_directory",
    "ingest_all_knowledge",
    "ingest_thread_specific_knowledge",
    "ingest_git_workflow_knowledge",
    "ingest_from_repomix_xml",
    "main",
    # From librarian
    "consult_knowledge_base",
    "ingest_knowledge",
    "bootstrap_knowledge",
    "list_knowledge_domains",
    "search_project_rules",
]
