"""
graph.py - Knowledge Graph Commands for Skill

Provides commands for:
- extract_entities: Extract entities and relations from text
- search_graph: Search the knowledge graph
- ingest_document: Ingest document with RAG processing

Usage:
    @omni("knowledge.extract_entities", {"source": "docs/api.md"})
    @omni("knowledge.search_graph", {"query": "architecture patterns"})
    @omni("knowledge.ingest_document", {"file_path": "docs/guide.pdf"})
"""

import asyncio
import json
import structlog
from pathlib import Path
from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.foundation.services.llm import get_llm_provider

logger = structlog.get_logger(__name__)


@skill_command(
    name="extract_entities",
    category="write",
    description="""
    Extract entities and relations from text or a document source.

    Uses LLM to identify named entities (PERSON, ORGANIZATION, CONCEPT, TOOL, etc.)
    and their relationships. Results can be stored in the knowledge graph.

    Args:
        - source: str - Text content or file path to analyze (required)
        - entity_types: list[str] - Optional list of entity types to extract
        - store: bool - Whether to store extracted entities in the graph (default: True)

    Returns:
        JSON with extracted entities and relations.
    """,
    autowire=True,
)
async def extract_entities(
    source: str,
    entity_types: list[str] | None = None,
    store: bool = True,
) -> str:
    """Extract entities and relations from text.

    Args:
        source: Text content or file path to analyze.
        entity_types: Optional list of entity types to focus on.
        store: Whether to store in the knowledge graph.
    """
    try:
        # Get content from file path or use directly
        if Path(source).exists() and Path(source).is_file():
            text = Path(source).read_text(encoding="utf-8")
            source_name = str(source)
        else:
            text = source
            source_name = "direct_input"

        # Check if knowledge graph is enabled
        from omni.rag.config import get_rag_config

        if not get_rag_config().knowledge_graph.enabled:
            return "Knowledge graph is disabled. Enable in settings.yaml to use entity extraction."

        # Get LLM provider
        provider = get_llm_provider()

        if not provider.is_available():
            return "LLM not configured. Enable inference settings in settings.yaml."

        # Create extractor with LLM provider
        from omni.rag.graph import KnowledgeGraphExtractor

        extractor = KnowledgeGraphExtractor(
            llm_complete_func=provider.complete_async,
            entity_types=entity_types,
        )

        # Extract entities
        entities, relations = await extractor.extract_entities(text, source_name)

        # Store if requested
        stored_entities = 0
        stored_relations = 0
        if store:
            from omni.rag.graph import get_graph_store

            store_instance = get_graph_store()
            for entity in entities:
                if store_instance.add_entity(entity):
                    stored_entities += 1
            for relation in relations:
                if store_instance.add_relation(relation):
                    stored_relations += 1

        # Format result
        result = {
            "source": source_name,
            "entities_extracted": len(entities),
            "relations_extracted": len(relations),
            "entities_stored": stored_entities,
            "relations_stored": stored_relations,
            "entities": [e.to_dict() for e in entities],
            "relations": [r.to_dict() for r in relations],
        }

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error("Entity extraction failed", error=str(e))
        raise


@skill_command(
    name="search_graph",
    category="search",
    description="""
    Search the knowledge graph for entities and their relationships.

    Supports multi-hop traversal to find related entities through relationship chains.

    Args:
        - query: str - Entity name or search query (required)
        - mode: str - Search mode: "entities", "relations", "multi_hop", or "hybrid" (default: "hybrid")
        - max_hops: int - Maximum hops for multi-hop search (default: 2)
        - limit: int - Maximum results to return (default: 20)

    Returns:
        JSON with matched entities and their relationships.
    """,
    autowire=True,
)
async def search_graph(
    query: str,
    mode: str = "hybrid",
    max_hops: int = 2,
    limit: int = 20,
) -> str:
    """Search the knowledge graph.

    Args:
        query: Entity name or search query.
        mode: Search mode (entities, relations, multi_hop, hybrid).
        max_hops: Maximum hops for multi-hop traversal.
        limit: Maximum results.
    """
    try:
        from omni.rag.config import get_rag_config

        if not get_rag_config().knowledge_graph.enabled:
            return "Knowledge graph is disabled."

        from omni.rag.graph import get_graph_store

        store = get_graph_store()

        # Check if Rust backend is available
        if store._backend is None:
            return "Rust knowledge backend is not available."

        results: dict[str, Any] = {"query": query, "mode": mode}

        if mode == "multi_hop":
            # Multi-hop graph traversal
            entities = store.multi_hop_search(
                start_entities=[query],
                max_hops=max_hops,
                limit=limit,
            )
            results["found_entities"] = entities
            results["hop_count"] = max_hops

        elif mode == "relations":
            # Search for relations
            relations = store.get_relations(entity_name=query)
            results["relations"] = relations

        elif mode == "entities":
            # Search for entity
            entity = store.get_entity(query)
            results["entity"] = entity

        else:  # hybrid
            # Combine entity lookup with multi-hop
            entity = store.get_entity(query)
            if entity:
                results["entity"] = entity

            related = store.multi_hop_search(
                start_entities=[query],
                max_hops=max_hops,
                limit=limit,
            )
            results["related_entities"] = related

            relations = store.get_relations(entity_name=query)
            results["relations"] = relations

        return json.dumps(results, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error("Graph search failed", error=str(e))
        raise


@skill_command(
    name="ingest_document",
    category="write",
    description="""
    Ingest a document with full RAG processing pipeline.

    Pipeline:
    1. Parse document (PDF, Markdown, etc.)
    2. Chunk content semantically
    3. Extract entities and relations
    4. Store in knowledge graph
    5. Generate embeddings for vector search

    Args:
        - file_path: str - Path to document (required)
        - chunking_strategy: str - Strategy: "sentence", "paragraph", "sliding_window", "semantic"
        - extract_entities: bool - Whether to extract entities (default: True)
        - store_in_graph: bool - Whether to store in knowledge graph (default: True)

    Returns:
        JSON with processing summary and stats.
    """,
    autowire=True,
)
async def ingest_document(
    file_path: str,
    chunking_strategy: str = "semantic",
    extract_entities: bool = True,
    store_in_graph: bool = True,
) -> str:
    """Ingest a document with full RAG pipeline.

    Args:
        file_path: Path to document to ingest.
        chunking_strategy: How to chunk the content.
        extract_entities: Whether to extract entities.
        store_in_graph: Whether to store in knowledge graph.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"File not found: {file_path}"

        # Step 1: Parse document
        from omni.rag.config import get_rag_config

        logger.info("Step 1/5: Parsing document", file=path.name)
        if get_rag_config().is_enabled("document_parsing"):
            try:
                from omni.rag.document import DocumentParser

                parser = DocumentParser()
                if parser:
                    content_blocks = await parser.parse(str(path))
                    text_content = "\n".join(block.get("text", "") for block in content_blocks)
                    logger.info("Document parsed", blocks=len(content_blocks))
                else:
                    text_content = path.read_text(encoding="utf-8")
            except Exception:
                text_content = path.read_text(encoding="utf-8")
        else:
            text_content = path.read_text(encoding="utf-8")

        if not text_content:
            return f"Failed to extract text from: {file_path}"

        # Step 2: Chunk content
        from omni.rag.chunking import create_chunker

        logger.info(
            "Step 2/5: Chunking content", strategy=chunking_strategy, chars=len(text_content)
        )
        chunker = create_chunker(chunking_strategy)
        chunks = await chunker.chunk(text_content)
        logger.info("Chunking completed", chunks=len(chunks))

        # Step 3: Extract entities (Parallelized with Semaphore)
        all_entities = []
        all_relations = []
        entities_extracted = 0
        relations_extracted = 0

        if extract_entities:
            provider = get_llm_provider()

            if not provider.is_available():
                logger.info("Step 3/5: Skipping entity extraction (no LLM configured)")
            else:
                from omni.rag.graph import KnowledgeGraphExtractor

                logger.info("Step 3/5: Extracting entities", chunks=len(chunks))
                extractor = KnowledgeGraphExtractor(
                    llm_complete_func=provider.complete_async,
                    entity_types=None,
                )
                # Limit concurrency to avoid timeouts/rate limits
                sem = asyncio.Semaphore(5)

                async def extract_with_limit(text: str, src: str):
                    async with sem:
                        return await extractor.extract_entities(text, source=src)

                # Create extraction tasks for all chunks
                tasks = []
                for chunk in chunks:
                    text = chunk.text if hasattr(chunk, "text") else str(chunk)
                    tasks.append(extract_with_limit(text, str(path)))

                # Execute in parallel (bounded)
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for i, res in enumerate(results):
                    if isinstance(res, Exception):
                        continue

                    ents, rels = res
                    all_entities.extend(ents)
                    all_relations.extend(rels)
                    entities_extracted += len(ents)
                    relations_extracted += len(rels)

                logger.info(
                    "Entity extraction completed",
                    entities=entities_extracted,
                    relations=relations_extracted,
                )

                # Step 4: Store in graph
                if store_in_graph:
                    from omni.rag.graph import get_graph_store

                    logger.info("Step 4/5: Storing in knowledge graph")
                    store = get_graph_store()
                    for entity in all_entities:
                        store.add_entity(entity)
                    for relation in all_relations:
                        store.add_relation(relation)
                    logger.info("Knowledge graph storage completed")

        # Step 5: Store in Vector Database (Embeddings)
        logger.info("Step 5/5: Storing in vector database", chunks=len(chunks))

        from omni.foundation import get_vector_store

        vector_store = get_vector_store()

        chunks_stored = 0
        vector_store_available = vector_store.store is not None

        if not vector_store_available:
            logger.warning("Vector store not available, skipping chunk storage")
        else:
            logger.info("Vector store connected, using batch storage")

            # Prepare batch data
            chunk_texts = []
            chunk_metas = []
            for i, chunk in enumerate(chunks):
                chunk_text = chunk.text if hasattr(chunk, "text") else str(chunk)
                meta = {
                    "source": str(path),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "title": path.name,
                }
                chunk_texts.append(chunk_text)
                chunk_metas.append(meta)

            # Use optimized batch storage
            chunks_stored = await vector_store.add_batch(
                chunk_texts,
                chunk_metas,
                collection="knowledge",
                batch_size=32,
            )

            logger.info("Vector storage completed", stored=chunks_stored, total=len(chunks))

        # Build result
        result = {
            "file": str(path),
            "chunks_created": len(chunks),
            "chunks_stored_in_vector_db": chunks_stored,
            "chunking_strategy": chunking_strategy,
            "entities_extracted": entities_extracted,
            "relations_extracted": relations_extracted,
            "stored_in_graph": store_in_graph,
            "total_chars": len(text_content),
        }

        logger.info(
            "Document ingestion completed",
            file=path.name,
            chunks=len(chunks),
            chunks_stored=chunks_stored,
            entities=entities_extracted,
            relations=relations_extracted,
        )

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error("Document ingestion failed", error=str(e))
        raise


@skill_command(
    name="graph_stats",
    category="read",
    description="""
    Get statistics about the knowledge graph.

    Returns:
        JSON with entity counts, relation counts, and backend info.
    """,
    autowire=True,
)
async def graph_stats() -> str:
    """Get knowledge graph statistics."""
    try:
        from omni.rag.graph import get_graph_store, KnowledgeGraphExtractor

        # Get store stats
        store = get_graph_store()
        stats: dict[str, Any] = {"backend": "rust" if store._backend else "none"}

        if store._backend:
            try:
                backend_stats = store._backend.get_stats()
                stats.update(backend_stats)
            except Exception:
                pass

        # Get extractor info
        extractor = KnowledgeGraphExtractor()
        stats["entity_types"] = extractor.entity_types
        stats["relation_types"] = extractor.relation_types

        return json.dumps(stats, indent=2, ensure_ascii=False)

    except Exception as e:
        return f"Failed to get graph stats: {e}"
