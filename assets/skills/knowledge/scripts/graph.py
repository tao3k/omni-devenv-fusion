"""
graph.py - Knowledge Graph Commands for Skill

Provides commands for:
- extract_entities: Extract entities and relations from text
- search_graph: Search the knowledge graph
- ingest_document: Ingest document with RAG processing (local path or PDF URL)

Usage:
    @omni("knowledge.extract_entities", {"source": "docs/api.md"})
    @omni("knowledge.search_graph", {"query": "architecture patterns"})
    @omni("knowledge.ingest_document", {"file_path": "docs/guide.pdf"})
    @omni("knowledge.ingest_document", {"file_path": "https://arxiv.org/pdf/2601.03192"})
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import structlog

from omni.foundation.api.decorators import skill_command, skill_resource
from omni.foundation.api.response_payloads import build_error_response
from omni.foundation.api.tool_context import run_with_heartbeat
from omni.foundation.runtime.skill_optimization import (
    resolve_bool_from_setting,
    resolve_int_from_setting,
)
from omni.foundation.services.llm import get_llm_provider

logger = structlog.get_logger(__name__)


def _entity_name(entity: Any) -> str:
    """Get entity name from dict or object."""
    if entity is None:
        return ""
    if isinstance(entity, dict):
        return (entity.get("name") or "").strip()
    return (getattr(entity, "name", None) or "").strip()


def _relation_endpoints(relation: Any) -> tuple[str, str]:
    """Get (source, target) from relation dict or object."""
    if relation is None:
        return ("", "")
    if isinstance(relation, dict):
        src = (relation.get("source") or "").strip()
        tgt = (relation.get("target") or "").strip()
        return (src, tgt)
    src = (getattr(relation, "source", None) or "").strip()
    tgt = (getattr(relation, "target", None) or "").strip()
    return (src, tgt)


def _relation_with_endpoints(relation: Any, source: str, target: str) -> Any:
    """Return a relation-like dict with given source/target for store.add_relation."""
    if isinstance(relation, dict):
        out = dict(relation)
        out["source"] = source
        out["target"] = target
        return out
    # Relation-like object: build dict expected by graph store
    return {
        "source": source,
        "target": target,
        "relation_type": getattr(relation, "relation_type", "RELATED_TO") or "RELATED_TO",
        "description": getattr(relation, "description", "") or "",
    }


async def write_entities_then_relations(
    store: Any,
    entities: list[Any],
    relations: list[Any],
) -> None:
    """Write all entities first, then all relations.

    Rust PyKnowledgeGraph requires source/target entities to exist before adding
    a relation. We resolve relation endpoints to existing entity names (case-
    insensitive) and add minimal CONCEPT entities for any missing endpoints
    so no relation is dropped with "Invalid relation".
    """

    def _write_entities() -> None:
        for entity in entities:
            store.add_entity(entity)

    await asyncio.to_thread(_write_entities)

    # Build canonical name set and case-insensitive lookup from written entities
    entity_names: set[str] = set()
    name_lower_to_canonical: dict[str, str] = {}
    for entity in entities:
        name = _entity_name(entity)
        if name:
            entity_names.add(name)
            name_lower_to_canonical[name.lower()] = name

    def _write_relations() -> None:
        for relation in relations:
            src, tgt = _relation_endpoints(relation)
            if not src or not tgt:
                continue
            source_canonical = name_lower_to_canonical.get(src.lower(), src)
            target_canonical = name_lower_to_canonical.get(tgt.lower(), tgt)
            # Ensure both endpoints exist (add placeholder CONCEPT if missing)
            for name in (source_canonical, target_canonical):
                if name not in entity_names:
                    store.add_entity(
                        {
                            "name": name,
                            "entity_type": "CONCEPT",
                            "description": "",
                        }
                    )
                    entity_names.add(name)
                    name_lower_to_canonical[name.lower()] = name
            to_store = _relation_with_endpoints(relation, source_canonical, target_canonical)
            store.add_relation(to_store)

    await asyncio.to_thread(_write_relations)


def _is_url(s: str) -> bool:
    """Return True if s looks like an http(s) URL."""
    s = (s or "").strip()
    return s.startswith("http://") or s.startswith("https://")


def _filename_from_url(url: str) -> str:
    """Derive a safe filename from URL (e.g. arxiv PDF -> 2601.03192.pdf)."""
    parsed = urlparse(url)
    path = (parsed.path or "").strip("/")
    # arXiv PDF: .../pdf/2601.03192 or .../2601.03192.pdf
    m = re.search(r"/(?:pdf/)?([0-9]{4}\.[0-9]{4,5})(?:\.pdf)?$", path, re.IGNORECASE)
    if m:
        return f"{m.group(1)}.pdf"
    if path:
        name = path.split("/")[-1]
        if name and "." in name:
            return name
        return f"{name}.pdf" if name else "document.pdf"
    return "document.pdf"


async def _download_to_project_data(url: str) -> Path:
    """Download URL to project data dir (PRJ_DATA/knowledge/downloads). Returns local Path."""
    from omni.foundation.config.prj import PRJ_DATA

    download_dir = PRJ_DATA.ensure_dir("knowledge", "downloads")
    filename = _filename_from_url(url)
    local_path = download_dir / filename
    if local_path.exists():
        logger.info("Using existing download", path=str(local_path), url=url)
        return local_path

    def _fetch() -> None:
        import urllib.request

        urllib.request.urlretrieve(url, str(local_path))

    logger.info("Downloading document to project data", url=url, path=str(local_path))
    await asyncio.to_thread(_fetch)
    return local_path


@skill_resource(
    name="graph_stats",
    description="Knowledge graph backend info: entity types, relation types, counts",
    resource_uri="omni://skill/knowledge/graph_stats",
)
def graph_stats_resource() -> dict:
    """Knowledge graph statistics as a resource."""
    try:
        from omni.rag.graph import get_graph_store

        store = get_graph_store()
        backend = store._backend
        if backend is None:
            return {"backend": "none"}

        stats_json = backend.get_stats()
        import json

        return json.loads(stats_json) if isinstance(stats_json, str) else stats_json
    except Exception as e:
        return build_error_response(error=str(e))


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
            return "Knowledge graph is disabled. Enable in settings (system: packages/conf/settings.yaml, user: $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml) to use entity extraction."

        # Get LLM provider
        provider = get_llm_provider()

        if not provider.is_available():
            return "LLM not configured. Enable inference settings in settings (system: packages/conf/settings.yaml, user: $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml)."

        # Create extractor with LLM provider
        from omni.rag.graph import KnowledgeGraphExtractor

        extractor = KnowledgeGraphExtractor(
            llm_complete_func=provider.complete_async,
            entity_types=entity_types,
        )

        # Extract entities with an explicit timeout guard to avoid hung runs.
        extraction_timeout_sec = resolve_int_from_setting(
            setting_key="knowledge.extract_entities_timeout_seconds",
            default=20,
            min_value=1,
            max_value=3600,
        )
        try:
            entities, relations = await asyncio.wait_for(
                extractor.extract_entities(text, source_name, timeout=extraction_timeout_sec),
                timeout=float(extraction_timeout_sec) + 1.0,
            )
        except TimeoutError:
            logger.warning(
                "Entity extraction timed out",
                source=source_name,
                timeout_sec=extraction_timeout_sec,
            )
            return json.dumps(
                {
                    "source": source_name,
                    "status": "timeout",
                    "timeout_sec": extraction_timeout_sec,
                    "entities_extracted": 0,
                    "relations_extracted": 0,
                    "entities_stored": 0,
                    "relations_stored": 0,
                    "entities": [],
                    "relations": [],
                },
                indent=2,
                ensure_ascii=False,
            )

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

    Accepts a local file path or a PDF URL (e.g. https://arxiv.org/pdf/2601.03192).
    When given a URL, the file is downloaded to project data (PRJ_DATA/knowledge/downloads)
    then processed.

    Pipeline:
    1. If file_path is a URL: download to project data dir
    2. Parse document (PDF, Markdown, etc.)
    3. Chunk content semantically
    4. Extract entities and relations
    5. Store in knowledge graph
    6. Generate embeddings for vector search

    Args:
        - file_path: str - Local path or PDF URL (required)
        - chunking_strategy: str - Strategy: "sentence", "paragraph", "sliding_window", "semantic"
        - extract_entities: bool - Whether to extract entities (default: False; set True for knowledge graph, can be slow)
        - store_in_graph: bool - Whether to store in knowledge graph (default: True)

    Returns:
        JSON with processing summary and stats.
    """,
    autowire=True,
)
async def ingest_document(
    file_path: str,
    chunking_strategy: str = "semantic",
    extract_entities: bool = False,
    store_in_graph: bool = True,
) -> str:
    """Ingest a document with full RAG pipeline.

    Args:
        file_path: Local path or PDF URL to ingest (URLs are downloaded to PRJ_DATA/knowledge/downloads).
        chunking_strategy: How to chunk the content.
        extract_entities: If True, extract entities (Step 3; can be slow with some LLM providers).
        store_in_graph: Whether to store in knowledge graph.
    """

    async def _ingest_body() -> str:
        if _is_url(file_path):
            path = await _download_to_project_data(file_path)
        else:
            path = Path(file_path)
        if not path.exists():
            return f"File not found: {file_path}"

        # Step 1: Parse document (configurable max_workers for Docling/BatchParser)
        from omni.rag.config import get_rag_config

        parse_max_workers = resolve_int_from_setting(
            setting_key="knowledge.ingest_parse_max_workers",
            default=4,
            min_value=1,
            max_value=32,
        )
        pdf_fast_path = resolve_bool_from_setting(
            setting_key="knowledge.ingest_pdf_fast_path",
            default=True,
        )

        logger.info(
            "Step 1/5: Parsing document",
            file=path.name,
            max_workers=parse_max_workers,
            pdf_fast_path=pdf_fast_path,
        )
        if get_rag_config().is_enabled("document_parsing"):
            try:
                from omni.rag.document import DocumentParser

                parser = DocumentParser()
                if parser:
                    content_blocks = await parser.parse(
                        str(path),
                        max_workers=parse_max_workers,
                        fast_path_for_pdf=pdf_fast_path,
                    )
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

        # Step 1.5: Optional PDF image extraction (UltraRAG build_image_corpus style)
        images_extracted: list[dict[str, Any]] = []
        extract_images = resolve_bool_from_setting(
            setting_key="knowledge.ingest_extract_images",
            default=False,
        )
        if extract_images and path.suffix.lower() == ".pdf":
            from omni.rag import extract_pdf_images

            images_extracted = await asyncio.to_thread(
                extract_pdf_images, str(path), dpi=150, format="png"
            )
            if images_extracted:
                logger.info(
                    "Step 1.5/5: Extracted PDF page images",
                    count=len(images_extracted),
                    source=path.name,
                )

        # Step 2: Chunk content (configurable size; CPU-bound strategies run in thread)
        chunk_target = resolve_int_from_setting(
            setting_key="knowledge.ingest_chunk_target_tokens",
            default=512,
            min_value=64,
            max_value=4096,
        )
        chunk_overlap = resolve_int_from_setting(
            setting_key="knowledge.ingest_chunk_overlap_tokens",
            default=50,
            min_value=0,
            max_value=1024,
        )

        logger.info(
            "Step 2/5: Chunking content",
            strategy=chunking_strategy,
            chars=len(text_content),
            target_tokens=chunk_target,
        )

        # Rust chunker is default; fallback to create_chunker when omni_core_rs unavailable
        chunks = None
        try:
            from types import SimpleNamespace

            import omni_core_rs

            def _rust_chunk() -> list:
                raw = omni_core_rs.py_chunk_text(
                    text_content,
                    chunk_size_tokens=chunk_target,
                    overlap_tokens=chunk_overlap,
                )
                return [SimpleNamespace(text=t, chunk_index=i) for t, i in raw]

            chunks = await asyncio.to_thread(_rust_chunk)
        except (ImportError, Exception) as e:
            logger.warning(
                "Rust chunker unavailable or failed (%s), falling back to create_chunker",
                e,
            )

        if chunks is None:
            from omni.rag.chunking import create_chunker

            chunker_kwargs: dict = {}
            if chunking_strategy in ("semantic", "sentence", "paragraph"):
                chunker_kwargs = {
                    "chunk_target_tokens": chunk_target,
                    "overlap_tokens": chunk_overlap,
                }
            chunker = create_chunker(chunking_strategy, **chunker_kwargs)
            if chunking_strategy in ("sentence", "paragraph", "sliding_window"):

                def _chunk_in_thread() -> list:
                    import asyncio

                    return asyncio.run(chunker.chunk(text_content))

                chunks = await asyncio.to_thread(_chunk_in_thread)  # CPU-bound, avoid blocking loop
            else:
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

                entity_concurrency = resolve_int_from_setting(
                    setting_key="knowledge.entity_extraction_concurrency",
                    default=8,
                    min_value=1,
                    max_value=64,
                )
                entity_sample_rate = resolve_int_from_setting(
                    setting_key="knowledge.entity_extraction_sample_rate",
                    default=1,
                    min_value=1,
                    max_value=1000,
                )
                entity_timeout = resolve_int_from_setting(
                    setting_key="knowledge.entity_extraction_timeout_seconds",
                    default=120,
                    min_value=1,
                    max_value=3600,
                )
                entity_max_chunks = resolve_int_from_setting(
                    setting_key="knowledge.entity_extraction_max_chunks",
                    default=12,
                    min_value=1,
                    max_value=10000,
                )

                # Cap chunks so Step 3 stays under ~30s and full pipeline under 1 min
                candidate = [i for i in range(len(chunks)) if i % entity_sample_rate == 0]
                indices_to_extract = candidate[:entity_max_chunks]
                total_calls = len(indices_to_extract)

                logger.info(
                    "Step 3/5: Extracting entities (LLM inference, not embedding)",
                    chunks=total_calls,
                    of_total=len(chunks),
                    max_chunks=entity_max_chunks,
                    concurrency=entity_concurrency,
                    timeout_sec=entity_timeout,
                )
                logger.info(
                    "Step 3/5: Dispatched; first wave starts now, completions stream as they finish",
                    tasks=total_calls,
                    concurrency=entity_concurrency,
                )
                extractor = KnowledgeGraphExtractor(
                    llm_complete_func=provider.complete_async,
                    entity_types=None,
                )
                try:
                    from omni.foundation.config.settings import get_setting

                    extraction_model = get_setting("knowledge.entity_extraction_model") or None
                    if extraction_model:
                        extractor._entity_extraction_model = str(extraction_model).strip()
                except Exception:
                    pass
                sem = asyncio.Semaphore(entity_concurrency)
                done_count: list[int] = [0]

                # Log "Starting chunk" for the first wave (up to concurrency) so logs reflect real parallelism
                first_wave = min(entity_concurrency, total_calls)

                async def extract_with_limit(idx: int, text: str, src: str):
                    text_len = len(text)
                    if idx < first_wave:
                        logger.info(
                            "Step 3/5: Starting chunk",
                            chunk_idx=idx,
                            text_chars=text_len,
                        )
                    async with sem:
                        try:
                            out = await asyncio.wait_for(
                                extractor.extract_entities(
                                    text, source=src, timeout=entity_timeout
                                ),
                                timeout=float(entity_timeout),
                            )
                        except TimeoutError:
                            logger.warning(
                                "Step 3/5: Chunk timeout, skipping entities",
                                chunk_idx=idx,
                                timeout_sec=entity_timeout,
                            )
                            out = ([], [])
                    done_count[0] += 1
                    if (
                        done_count[0] == 1
                        or done_count[0] % 10 == 0
                        or done_count[0] == total_calls
                    ):
                        logger.info(
                            "Step 3/5: Extracting entities",
                            progress=f"{done_count[0]}/{total_calls}",
                        )
                    return (idx, out)

                tasks = [
                    extract_with_limit(
                        idx,
                        chunks[idx].text if hasattr(chunks[idx], "text") else str(chunks[idx]),
                        str(path),
                    )
                    for idx in indices_to_extract
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for i, r in enumerate(results):
                    if isinstance(r, Exception):
                        logger.warning(
                            "Step 3/5: Chunk extraction failed",
                            chunk_idx=indices_to_extract[i] if i < len(indices_to_extract) else i,
                            error=str(r),
                        )
                        continue
                    _, (ents, rels) = r
                    all_entities.extend(ents)
                    all_relations.extend(rels)
                    entities_extracted += len(ents)
                    relations_extracted += len(rels)

                logger.info(
                    "Entity extraction completed",
                    entities=entities_extracted,
                    relations=relations_extracted,
                )
                logger.info("Step 3/5: Done; proceeding to Step 4/5 (graph) and Step 5/5 (vectors)")

        # Embedding batch size (larger = fewer round-trips; tune if OOM)
        embed_batch_size = resolve_int_from_setting(
            setting_key="knowledge.ingest_embed_batch_size",
            default=64,
            min_value=1,
            max_value=2048,
        )
        embed_parallel_batches = resolve_int_from_setting(
            setting_key="knowledge.ingest_embed_parallel_batches",
            default=2,
            min_value=1,
            max_value=64,
        )

        # Prepare chunk payload once for Step 5
        chunk_texts = []
        chunk_metas = []
        for i, chunk in enumerate(chunks):
            chunk_text = chunk.text if hasattr(chunk, "text") else str(chunk)
            chunk_texts.append(chunk_text)
            chunk_metas.append(
                {
                    "source": str(path),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "title": path.name,
                }
            )

        from omni.foundation import get_vector_store

        vector_store = get_vector_store()
        vector_store_available = vector_store.store is not None

        async def _store_graph() -> None:
            if not store_in_graph or (not all_entities and not all_relations):
                return
            from omni.rag.graph import get_graph_store

            store = get_graph_store()
            parallel_graph = resolve_bool_from_setting(
                setting_key="knowledge.ingest_graph_parallel_writes",
                default=False,
            )

            if parallel_graph:
                logger.info(
                    "Step 4/5: Storing in knowledge graph (entities then relations)",
                    entities=len(all_entities),
                    relations=len(all_relations),
                )
                await write_entities_then_relations(store, all_entities, all_relations)
            else:
                logger.info("Step 4/5: Storing in knowledge graph")
                await write_entities_then_relations(store, all_entities, all_relations)
            logger.info("Knowledge graph storage completed")

        async def _store_vectors() -> int:
            if not vector_store_available:
                return 0
            # Idempotent ingest: delete existing chunks for this source before add
            source_str = str(path)
            deleted = await vector_store.delete_by_metadata_source(
                collection="knowledge_chunks", source=source_str
            )
            if deleted > 0:
                logger.info(
                    "Deleted existing chunks for re-ingest", source=source_str, deleted=deleted
                )
            logger.info(
                "Step 5/5: Storing in vector database",
                chunks=len(chunks),
                embed_batch_size=embed_batch_size,
                parallel_batches=embed_parallel_batches,
            )
            n = await vector_store.add_batch(
                chunk_texts,
                chunk_metas,
                collection="knowledge_chunks",
                batch_size=embed_batch_size,
                max_concurrent_embed_batches=embed_parallel_batches,
            )
            logger.info("Vector storage completed", stored=n, total=len(chunks))
            return n

        chunks_stored = 0
        if not vector_store_available:
            logger.warning("Vector store not available, skipping chunk storage")
        if store_in_graph and (all_entities or all_relations) and vector_store_available:
            _, chunks_stored = await asyncio.gather(_store_graph(), _store_vectors())
        elif store_in_graph and (all_entities or all_relations):
            await _store_graph()
        elif vector_store_available:
            chunks_stored = await _store_vectors()

        # Persist image paths for this source so recall (full_document) can return them
        image_paths_list: list[str] = [e["image_path"] for e in images_extracted]
        if image_paths_list:
            try:
                import json as _json

                from omni.foundation import PRJ_CACHE

                manifest_path = PRJ_CACHE("omni-vector", "image_manifests.json")
                manifest_path = (
                    manifest_path if isinstance(manifest_path, str) else str(manifest_path)
                )
                manifest: dict[str, list[str]] = {}
                if Path(manifest_path).exists():
                    manifest = _json.loads(Path(manifest_path).read_text(encoding="utf-8"))
                manifest[str(path)] = image_paths_list
                Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
                Path(manifest_path).write_text(_json.dumps(manifest, indent=2), encoding="utf-8")
            except Exception as e:
                logger.warning("Could not write image manifest", error=str(e))

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
            "images_extracted": len(images_extracted),
            "image_paths": image_paths_list,
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

    try:
        return await run_with_heartbeat(_ingest_body())
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
        from omni.rag.graph import KnowledgeGraphExtractor, get_graph_store

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
