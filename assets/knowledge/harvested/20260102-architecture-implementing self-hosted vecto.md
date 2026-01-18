# [ARCHIVAL] Implementing Self-Hosted Vector Database for RAG via ChromaDB Integration

> **WARNING**: This document describes OLD architecture that has been migrated to LanceDB.
> Current implementation uses omni-vector (Rust + LanceDB). See `docs/reference/librarian.md`.

**Category**: architecture
**Date**: 2026-01-02
**Harvested**: Automatically from development session
**Status**: OBSOLETE - Migrated to LanceDB

## Context

Phase 11 required implementing a Neural Matrix system with RAG capabilities. The challenge was choosing a vector database solution that could be self-hosted to avoid external dependencies while providing efficient vector search and knowledge management capabilities for the Tri-MCP system.

## Solution (OLD - See Warning Above)

Selected ChromaDB as the vector database backend and integrated it through a new Librarian capability.

## Key Takeaways

- Self-hosted vector databases provide better control and zero external dependencies (now via LanceDB)
- Integrating RAG capabilities through a dedicated capability (Librarian) follows clean architecture principles by keeping vector operations encapsulated
- Separating vector storage (vector_store.py) from capability orchestration (librarian.py) enables better maintainability and testing
- Persistent storage configuration is crucial for vector databases to maintain knowledge continuity across restarts
