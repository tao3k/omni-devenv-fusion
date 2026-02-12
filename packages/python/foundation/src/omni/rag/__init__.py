"""
omni.rag - RAG Module for Omni-Dev Fusion

Provides RAG capabilities with modular design:
- Semantic text chunking
- Entity and relation extraction
- Knowledge graph storage
- Multimodal processing (images, tables, formulas)
- Zettelkasten (zk) integration for bidirectional note links
- Knowledge graph analyzer (PyArrow/Polars)

Modules:
- config.py: Module configuration with feature flags
- chunking.py: Semantic text chunking
- entities.py: Entity and Relation types
- graph.py: Knowledge graph and entity extraction
- multimodal.py: Image, table, and formula processing
- zk_client.py: Full-featured async zk CLI wrapper
- zk_integration.py: Legacy zk integration (wraps zk_client)
- zk_navigator.py: Graph-based reasoning search navigator
- zk_search.py: Reasoning-based ZK search (PageIndex-style)
- unified_knowledge.py: zk notebook integration
- analyzer.py: Knowledge graph analyzer (PyArrow/Polars)
"""

from .config import (
    RAGConfig,
    DocumentParsingConfig,
    MultimodalConfig,
    KnowledgeGraphConfig,
    RustSearchConfig,
    get_rag_config,
    get_parser,
    is_knowledge_graph_enabled,
    is_multimodal_enabled,
)
from .chunking import (
    Chunk,
    SemanticChunker,
    SentenceChunker,
    ParagraphChunker,
    SlidingWindowChunker,
    create_chunker,
    chunk_text,
)
from .entities import (
    Entity,
    Relation,
    EntityMention,
    ExtractedChunk,
    EntityType,
    RelationType,
)
from .graph import (
    KnowledgeGraphExtractor,
    KnowledgeGraphStore,
    EXTRACT_ENTITIES_PROMPT,
    EXTRACT_ENTITIES_PROMPT_EN,
    EXTRACT_ENTITIES_PROMPT_ZH,
    get_graph_extractor,
    get_graph_store,
)
from .multimodal import (
    ImageProcessor,
    ImageResult,
    TableExtractor,
    TableResult,
    FormulaParser,
    FormulaResult,
    MultimodalProcessor,
    CONTENT_TYPE_IMAGE,
    CONTENT_TYPE_TABLE,
    CONTENT_TYPE_FORMULA,
    get_image_processor,
    get_table_extractor,
    get_formula_parser,
    get_multimodal_processor,
    process_image,
    process_table,
    process_formula,
    extract_formulas,
)
from .zk_client import (
    ZkNote,
    ZkClient,
    ZkListConfig,
    get_zk_client,
)
from .zk_navigator import (
    NavigationConfig,
    ZkGraphNavigator,
    get_zk_navigator,
)
from .zk_integration import (
    ZkLink,
    ZkEntityRef,
    RustEntityZkRef,
)
from .zk_search import (
    ZkSearchResult,
    ZkSearchConfig,
    ZkReasoningSearcher,
    ZkHybridSearcher,
    get_zk_searcher,
    get_zk_hybrid_searcher,
)
from .unified_knowledge import (
    UnifiedEntity,
    UnifiedKnowledgeManager,
    get_unified_manager,
)
from .analyzer import (
    KnowledgeGraphAnalyzer,
    GraphAnalysisResult,
    load_and_analyze,
    create_entities_dataframe,
    create_relations_dataframe,
    analyze_entity_types,
    analyze_connections,
    POLARS_AVAILABLE,
)
from .retrieval import (
    RetrievalResult,
    RetrievalConfig,
    RetrievalBackend,
    HybridRetrievalUnavailableError,
    LanceRetrievalBackend,
    HybridRetrievalBackend,
    create_retriever_node,
    create_hybrid_node,
    create_retrieval_backend,
)

__all__ = [
    # Configuration
    "RAGConfig",
    "DocumentParsingConfig",
    "MultimodalConfig",
    "KnowledgeGraphConfig",
    "RustSearchConfig",
    "get_rag_config",
    "get_parser",
    "is_knowledge_graph_enabled",
    "is_multimodal_enabled",
    # Chunking
    "Chunk",
    "SemanticChunker",
    "SentenceChunker",
    "ParagraphChunker",
    "SlidingWindowChunker",
    "create_chunker",
    "chunk_text",
    # Entities and Relations
    "Entity",
    "Relation",
    "EntityMention",
    "ExtractedChunk",
    "EntityType",
    "RelationType",
    # Knowledge Graph
    "KnowledgeGraphExtractor",
    "KnowledgeGraphStore",
    "EXTRACT_ENTITIES_PROMPT",
    "EXTRACT_ENTITIES_PROMPT_EN",
    "EXTRACT_ENTITIES_PROMPT_ZH",
    "get_graph_extractor",
    "get_graph_store",
    # Multimodal
    "ImageProcessor",
    "ImageResult",
    "TableExtractor",
    "TableResult",
    "FormulaParser",
    "FormulaResult",
    "MultimodalProcessor",
    "CONTENT_TYPE_IMAGE",
    "CONTENT_TYPE_TABLE",
    "CONTENT_TYPE_FORMULA",
    "get_image_processor",
    "get_table_extractor",
    "get_formula_parser",
    "get_multimodal_processor",
    "process_image",
    "process_table",
    "process_formula",
    "extract_formulas",
    # Zk Client (full-featured async wrapper)
    "ZkNote",
    "ZkClient",
    "ZkListConfig",
    "get_zk_client",
    # Zk Navigator (graph-based reasoning)
    "NavigationConfig",
    "ZkGraphNavigator",
    "get_zk_navigator",
    # Zk Integration (link types)
    "ZkLink",
    "ZkEntityRef",
    "RustEntityZkRef",
    # ZK Reasoning Search (PageIndex-style)
    "ZkSearchResult",
    "ZkSearchConfig",
    "ZkReasoningSearcher",
    "ZkHybridSearcher",
    "get_zk_searcher",
    "get_zk_hybrid_searcher",
    # Unified Knowledge (zk-based)
    "UnifiedEntity",
    "UnifiedKnowledgeManager",
    "get_unified_manager",
    # Knowledge Graph Analyzer (PyArrow/Polars)
    "KnowledgeGraphAnalyzer",
    "GraphAnalysisResult",
    "load_and_analyze",
    "create_entities_dataframe",
    "create_relations_dataframe",
    "analyze_entity_types",
    "analyze_connections",
    "POLARS_AVAILABLE",
    # Retrieval Backends
    "RetrievalResult",
    "RetrievalConfig",
    "RetrievalBackend",
    "HybridRetrievalUnavailableError",
    "LanceRetrievalBackend",
    "HybridRetrievalBackend",
    "create_retriever_node",
    "create_hybrid_node",
    "create_retrieval_backend",
]
