"""
config.py - RAG Module Configuration

Provides comprehensive configuration for RAG-Anything integration with feature flags
for modular enable/disable of each capability.

Configuration Structure:
- RAGConfig: Main configuration container
- DocumentParsingConfig: PDF/Document parsing settings
- MultimodalConfig: Image/Table/Formula processing settings
- KnowledgeGraphConfig: Entity extraction and knowledge graph settings
- RustSearchConfig: Rust-backed search enhancements

Usage:
    from omni.rag.config import get_rag_config, RAGConfig

    config = get_rag_config()
    if config.document_parsing.enabled:
        parser = get_parser()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class DocumentParsingConfig:
    """Configuration for document parsing capabilities.

    Attributes:
        enabled: Enable document parsing (PDF, Office, etc.)
        parser: Default parser (docling, mineru, auto)
        max_workers: Maximum parallel workers for batch processing
        show_progress: Show progress bars during processing
        supported_formats: List of supported file extensions
    """

    enabled: bool = True
    parser: str = "docling"
    max_workers: int = 4
    show_progress: bool = True
    supported_formats: list[str] = field(
        default_factory=lambda: [
            ".pdf",
            ".docx",
            ".pptx",
            ".xlsx",
            ".md",
            ".txt",
            ".png",
            ".jpg",
            ".jpeg",
        ]
    )


@dataclass
class MultimodalConfig:
    """Configuration for multimodal content processing.

    Attributes:
        enabled: Enable multimodal processing (images, tables, equations)
        vision_model: Vision-language model for image analysis
        table_processor: Table processing method (auto, struct)
        equation_processor: Equation processing method (auto, latex)
        ocr_enabled: Enable OCR for scanned documents
    """

    enabled: bool = False
    vision_model: str = "gpt-4o"
    table_processor: str = "auto"
    equation_processor: str = "auto"
    ocr_enabled: bool = True


@dataclass
class KnowledgeGraphConfig:
    """Configuration for knowledge graph and entity extraction.

    Attributes:
        enabled: Enable knowledge graph and entity extraction
        entity_types: List of entity types to extract
        extraction_llm: LLM for entity extraction (None = use default)
        store_in_rust: Store entities in Rust xiuxian-wendao crate
        max_entities_per_doc: Maximum entities per document
        relation_types: List of relation types to extract
    """

    enabled: bool = True
    entity_types: list[str] = field(
        default_factory=lambda: [
            "PERSON",
            "ORGANIZATION",
            "CONCEPT",
            "PROJECT",
            "TOOL",
            "SKILL",
        ]
    )
    extraction_llm: str | None = None
    store_in_rust: bool = True
    max_entities_per_doc: int = 100
    relation_types: list[str] = field(
        default_factory=lambda: [
            "WORKS_FOR",
            "PART_OF",
            "USES",
            "DEPENDS_ON",
            "SIMILAR_TO",
        ]
    )


@dataclass
class RustSearchConfig:
    """Configuration for Rust-backed search enhancements.

    Attributes:
        enabled: Enable Rust vector store integration
        entity_aware: Enable entity-aware hybrid search
        rerank: Enable re-ranking of search results
        hybrid_v2: Use second-generation hybrid search (semantic + BM25 + entity)
        rrf_k: RRF fusion constant (default: 60)
    """

    enabled: bool = True
    entity_aware: bool = True
    rerank: bool = True
    hybrid_v2: bool = True
    rrf_k: int = 60


@dataclass
class RAGConfig:
    """Main RAG module configuration.

    Provides feature flags for modular enable/disable of RAG capabilities.

    Attributes:
        enabled: Master switch for the entire RAG module
        document_parsing: Document parsing configuration
        multimodal: Multimodal processing configuration
        knowledge_graph: Knowledge graph configuration
        rust_search: Rust search enhancement configuration
    """

    enabled: bool = True
    document_parsing: DocumentParsingConfig = field(default_factory=DocumentParsingConfig)
    multimodal: MultimodalConfig = field(default_factory=MultimodalConfig)
    knowledge_graph: KnowledgeGraphConfig = field(default_factory=KnowledgeGraphConfig)
    rust_search: RustSearchConfig = field(default_factory=RustSearchConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RAGConfig:
        """Create RAGConfig from a dictionary (e.g., from settings).

        Args:
            data: Dictionary with optional configuration sections.

        Returns:
            RAGConfig instance with merged system+user settings.
        """
        # Extract sub-configurations if present
        doc_parse_cfg = DocumentParsingConfig()
        multimodal_cfg = MultimodalConfig()
        kg_cfg = KnowledgeGraphConfig()
        rust_cfg = RustSearchConfig()

        if "document_parsing" in data:
            doc_data = data["document_parsing"]
            doc_parse_cfg = DocumentParsingConfig(
                enabled=doc_data.get("enabled", doc_parse_cfg.enabled),
                parser=doc_data.get("parser", doc_parse_cfg.parser),
                max_workers=doc_data.get("max_workers", doc_parse_cfg.max_workers),
                show_progress=doc_data.get("show_progress", doc_parse_cfg.show_progress),
            )

        if "multimodal" in data:
            multimodal_data = data["multimodal"]
            multimodal_cfg = MultimodalConfig(
                enabled=multimodal_data.get("enabled", multimodal_cfg.enabled),
                vision_model=multimodal_data.get("vision_model", multimodal_cfg.vision_model),
                table_processor=multimodal_data.get(
                    "table_processor", multimodal_cfg.table_processor
                ),
                equation_processor=multimodal_data.get(
                    "equation_processor", multimodal_cfg.equation_processor
                ),
            )

        if "knowledge_graph" in data:
            kg_data = data["knowledge_graph"]
            kg_cfg = KnowledgeGraphConfig(
                enabled=kg_data.get("enabled", kg_cfg.enabled),
                entity_types=kg_data.get("entity_types", kg_cfg.entity_types),
                extraction_llm=kg_data.get("extraction_llm", kg_cfg.extraction_llm),
                store_in_rust=kg_data.get("store_in_rust", kg_cfg.store_in_rust),
                max_entities_per_doc=kg_data.get(
                    "max_entities_per_doc", kg_cfg.max_entities_per_doc
                ),
                relation_types=kg_data.get("relation_types", kg_cfg.relation_types),
            )

        if "rust_search" in data:
            rust_data = data["rust_search"]
            rust_cfg = RustSearchConfig(
                enabled=rust_data.get("enabled", rust_cfg.enabled),
                entity_aware=rust_data.get("entity_aware", rust_cfg.entity_aware),
                rerank=rust_data.get("rerank", rust_cfg.rerank),
                hybrid_v2=rust_data.get("hybrid_v2", rust_cfg.hybrid_v2),
                rrf_k=rust_data.get("rrf_k", rust_cfg.rrf_k),
            )

        return cls(
            enabled=data.get("enabled", True),
            document_parsing=doc_parse_cfg,
            multimodal=multimodal_cfg,
            knowledge_graph=kg_cfg,
            rust_search=rust_cfg,
        )

    def is_enabled(self, module: str) -> bool:
        """Check if a specific module is enabled.

        Args:
            module: Module name (document_parsing, multimodal, knowledge_graph, rust_search)

        Returns:
            True if the module is enabled.
        """
        if not self.enabled:
            return False

        module_configs = {
            "document_parsing": self.document_parsing,
            "multimodal": self.multimodal,
            "knowledge_graph": self.knowledge_graph,
            "rust_search": self.rust_search,
        }

        config = module_configs.get(module)
        if config is None:
            return False

        return getattr(config, "enabled", False)


# Module-level cache
_rag_config: RAGConfig | None = None


def get_rag_config() -> RAGConfig:
    """Get the RAG configuration singleton.

    Loads configuration from settings (system: packages/conf/settings.yaml, user: $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml) if available,
    otherwise returns default configuration.

    Returns:
        RAGConfig instance with current settings.
    """
    global _rag_config

    if _rag_config is not None:
        return _rag_config

    # Try to load from settings
    try:
        from omni.foundation.config.settings import get_setting

        rag_settings = get_setting("rag") or {}
        if rag_settings:
            _rag_config = RAGConfig.from_dict(rag_settings)
            logger.info(
                "RAG config loaded from settings",
                enabled=_rag_config.enabled,
            )
        else:
            _rag_config = RAGConfig()
            logger.info("RAG config using defaults")
    except ImportError:
        _rag_config = RAGConfig()
        logger.info("RAG config using defaults (settings unavailable)")

    return _rag_config


def reload_rag_config() -> RAGConfig:
    """Force reload RAG configuration from settings.

    Returns:
        Fresh RAGConfig instance.
    """
    global _rag_config
    _rag_config = None
    return get_rag_config()


def get_parser(name: str | None = None) -> str | None:
    """Get the configured document parser.

    Args:
        name: Optional parser name override.

    Returns:
        Parser name string or None if parsing is disabled.
    """
    config = get_rag_config()
    if not config.is_enabled("document_parsing"):
        return None
    return name or config.document_parsing.parser


def is_knowledge_graph_enabled() -> bool:
    """Check if knowledge graph extraction is enabled.

    Returns:
        True if knowledge_graph is enabled.
    """
    return get_rag_config().is_enabled("knowledge_graph")


def is_multimodal_enabled() -> bool:
    """Check if multimodal processing is enabled.

    Returns:
        True if multimodal is enabled.
    """
    return get_rag_config().is_enabled("multimodal")


__all__ = [
    "RAGConfig",
    "DocumentParsingConfig",
    "MultimodalConfig",
    "KnowledgeGraphConfig",
    "RustSearchConfig",
    "get_rag_config",
    "reload_rag_config",
    "get_parser",
    "is_knowledge_graph_enabled",
    "is_multimodal_enabled",
]
