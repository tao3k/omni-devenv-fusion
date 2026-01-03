# Implementing Self-Hosted Vector Database for RAG via ChromaDB Integration

**Category**: architecture
**Date**: 2026-01-02
**Harvested**: Automatically from development session

## Context
Phase 11 required implementing a Neural Matrix system with RAG capabilities. The challenge was choosing a vector database solution that could be self-hosted to avoid external dependencies while providing efficient vector search and knowledge management capabilities for the Tri-MCP system.

## Solution
Selected ChromaDB as the vector database backend and integrated it through a new Librarian capability in the orchestrator. This provided persistent storage, vector search functionality, and knowledge ingestion/retrieval tools (consult_knowledge_base and ingest_knowledge) while maintaining zero external service dependencies.

## Key Takeaways
- Self-hosted vector databases like ChromaDB provide better control and zero external dependencies compared to managed services like Pinecone
- Integrating RAG capabilities through a dedicated capability (Librarian) follows clean architecture principles by keeping vector operations encapsulated
- Separating vector storage (vector_store.py) from capability orchestration (librarian.py) enables better maintainability and testing
- Persistent storage configuration is crucial for vector databases to maintain knowledge continuity across restarts

## Pattern / Snippet
```architecture
# Vector store initialization with persistent storage
from chromadb.config import Settings

class VectorStore:
    def __init__(self, persist_directory="./chroma_db"):
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
    
    def ingest_knowledge(self, documents, collection_name="knowledge"):
        collection = self.client.get_or_create_collection(collection_name)
        # Implementation for document ingestion
        
    def consult_knowledge_base(self, query, n_results=5):
        collection = self.client.get_or_create_collection("knowledge")
        # Implementation for vector search and retrieval
```

## Related Files
- `src/agent/core/vector_store.py`
- `src/agent/capabilities/librarian.py`