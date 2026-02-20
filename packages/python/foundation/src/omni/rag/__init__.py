"""Public RAG namespace with lazy exports for lower startup overhead."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "CONTENT_TYPE_FORMULA": (".multimodal", "CONTENT_TYPE_FORMULA"),
    "CONTENT_TYPE_IMAGE": (".multimodal", "CONTENT_TYPE_IMAGE"),
    "CONTENT_TYPE_TABLE": (".multimodal", "CONTENT_TYPE_TABLE"),
    "Chunk": (".chunking", "Chunk"),
    "DocumentParsingConfig": (".config", "DocumentParsingConfig"),
    "EXTRACT_ENTITIES_PROMPT": (".graph", "EXTRACT_ENTITIES_PROMPT"),
    "EXTRACT_ENTITIES_PROMPT_EN": (".graph", "EXTRACT_ENTITIES_PROMPT_EN"),
    "EXTRACT_ENTITIES_PROMPT_ZH": (".graph", "EXTRACT_ENTITIES_PROMPT_ZH"),
    "Entity": (".entities", "Entity"),
    "EntityMention": (".entities", "EntityMention"),
    "EntityType": (".entities", "EntityType"),
    "ExtractedChunk": (".entities", "ExtractedChunk"),
    "FormulaParser": (".multimodal", "FormulaParser"),
    "FormulaResult": (".multimodal", "FormulaResult"),
    "GraphAnalysisResult": (".analyzer", "GraphAnalysisResult"),
    "HybridRetrievalBackend": (".retrieval", "HybridRetrievalBackend"),
    "HybridRetrievalUnavailableError": (".retrieval", "HybridRetrievalUnavailableError"),
    "ImageProcessor": (".multimodal", "ImageProcessor"),
    "ImageResult": (".multimodal", "ImageResult"),
    "KnowledgeGraphAnalyzer": (".analyzer", "KnowledgeGraphAnalyzer"),
    "KnowledgeGraphConfig": (".config", "KnowledgeGraphConfig"),
    "KnowledgeGraphExtractor": (".graph", "KnowledgeGraphExtractor"),
    "KnowledgeGraphStore": (".graph", "KnowledgeGraphStore"),
    "LanceRetrievalBackend": (".retrieval", "LanceRetrievalBackend"),
    "MultimodalConfig": (".config", "MultimodalConfig"),
    "MultimodalProcessor": (".multimodal", "MultimodalProcessor"),
    "NavigationConfig": (".link_graph_navigator", "NavigationConfig"),
    "POLARS_AVAILABLE": (".analyzer", "POLARS_AVAILABLE"),
    "ParagraphChunker": (".chunking", "ParagraphChunker"),
    "RAGConfig": (".config", "RAGConfig"),
    "Relation": (".entities", "Relation"),
    "RelationType": (".entities", "RelationType"),
    "RetrievalBackend": (".retrieval", "RetrievalBackend"),
    "RetrievalConfig": (".retrieval", "RetrievalConfig"),
    "RetrievalResult": (".retrieval", "RetrievalResult"),
    "RustSearchConfig": (".config", "RustSearchConfig"),
    "SemanticChunker": (".chunking", "SemanticChunker"),
    "SentenceChunker": (".chunking", "SentenceChunker"),
    "SlidingWindowChunker": (".chunking", "SlidingWindowChunker"),
    "TableExtractor": (".multimodal", "TableExtractor"),
    "TableResult": (".multimodal", "TableResult"),
    "UnifiedEntity": (".unified_knowledge", "UnifiedEntity"),
    "UnifiedKnowledgeManager": (".unified_knowledge", "UnifiedKnowledgeManager"),
    "LinkGraphNavigator": (".link_graph_navigator", "LinkGraphNavigator"),
    "analyze_connections": (".analyzer", "analyze_connections"),
    "analyze_entity_types": (".analyzer", "analyze_entity_types"),
    "apply_kg_recall_boost": (".dual_core", "apply_kg_recall_boost"),
    "chunk_text": (".chunking", "chunk_text"),
    "compute_fusion_weights": (".dual_core", "compute_fusion_weights"),
    "create_chunker": (".chunking", "create_chunker"),
    "create_entities_dataframe": (".analyzer", "create_entities_dataframe"),
    "create_hybrid_node": (".retrieval", "create_hybrid_node"),
    "create_relations_dataframe": (".analyzer", "create_relations_dataframe"),
    "create_retrieval_backend": (".retrieval", "create_retrieval_backend"),
    "create_retriever_node": (".retrieval", "create_retriever_node"),
    "enrich_skill_graph_from_link_graph": (".dual_core", "enrich_skill_graph_from_link_graph"),
    "extract_formulas": (".multimodal", "extract_formulas"),
    "extract_pdf_images": (".pdf_images", "extract_pdf_images"),
    "get_formula_parser": (".multimodal", "get_formula_parser"),
    "get_graph_extractor": (".graph", "get_graph_extractor"),
    "get_graph_store": (".graph", "get_graph_store"),
    "get_image_processor": (".multimodal", "get_image_processor"),
    "get_multimodal_processor": (".multimodal", "get_multimodal_processor"),
    "get_parser": (".config", "get_parser"),
    "get_rag_config": (".config", "get_rag_config"),
    "get_table_extractor": (".multimodal", "get_table_extractor"),
    "get_unified_manager": (".unified_knowledge", "get_unified_manager"),
    "get_link_graph_navigator": (".link_graph_navigator", "get_link_graph_navigator"),
    "is_knowledge_graph_enabled": (".config", "is_knowledge_graph_enabled"),
    "is_multimodal_enabled": (".config", "is_multimodal_enabled"),
    "load_and_analyze": (".analyzer", "load_and_analyze"),
    "process_formula": (".multimodal", "process_formula"),
    "process_image": (".multimodal", "process_image"),
    "process_table": (".multimodal", "process_table"),
    "register_skill_entities": (".dual_core", "register_skill_entities"),
    "link_graph_proximity_boost": (".dual_core", "link_graph_proximity_boost"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name, package=__name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
