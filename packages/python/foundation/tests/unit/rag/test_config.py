"""
Tests for omni.rag.config module.
"""

import pytest


class TestDocumentParsingConfig:
    """Test DocumentParsingConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        from omni.rag.config import DocumentParsingConfig

        config = DocumentParsingConfig()
        assert config.enabled is True
        assert config.parser == "docling"
        assert config.max_workers == 4
        assert config.show_progress is True
        assert ".pdf" in config.supported_formats

    def test_custom_values(self):
        """Test custom configuration values."""
        from omni.rag.config import DocumentParsingConfig

        config = DocumentParsingConfig(
            enabled=False,
            parser="mineru",
            max_workers=8,
            show_progress=False,
        )
        assert config.enabled is False
        assert config.parser == "mineru"
        assert config.max_workers == 8
        assert config.show_progress is False


class TestMultimodalConfig:
    """Test MultimodalConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        from omni.rag.config import MultimodalConfig

        config = MultimodalConfig()
        assert config.enabled is False
        assert config.vision_model == "gpt-4o"
        assert config.table_processor == "auto"
        assert config.equation_processor == "auto"
        assert config.ocr_enabled is True

    def test_custom_values(self):
        """Test custom configuration values."""
        from omni.rag.config import MultimodalConfig

        config = MultimodalConfig(
            enabled=True,
            vision_model="claude-sonnet-4",
            ocr_enabled=False,
        )
        assert config.enabled is True
        assert config.vision_model == "claude-sonnet-4"
        assert config.ocr_enabled is False


class TestKnowledgeGraphConfig:
    """Test KnowledgeGraphConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        from omni.rag.config import KnowledgeGraphConfig

        config = KnowledgeGraphConfig()
        assert config.enabled is True
        assert "PERSON" in config.entity_types
        assert "ORGANIZATION" in config.entity_types
        assert config.store_in_rust is True
        assert config.max_entities_per_doc == 100

    def test_custom_values(self):
        """Test custom configuration values."""
        from omni.rag.config import KnowledgeGraphConfig

        config = KnowledgeGraphConfig(
            enabled=False,
            entity_types=["PERSON", "ORG"],
            store_in_rust=False,
            max_entities_per_doc=50,
        )
        assert config.enabled is False
        assert len(config.entity_types) == 2
        assert config.store_in_rust is False
        assert config.max_entities_per_doc == 50


class TestRustSearchConfig:
    """Test RustSearchConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        from omni.rag.config import RustSearchConfig

        config = RustSearchConfig()
        assert config.enabled is True
        assert config.entity_aware is True
        assert config.rerank is True
        assert config.hybrid_v2 is True
        assert config.rrf_k == 60

    def test_custom_values(self):
        """Test custom configuration values."""
        from omni.rag.config import RustSearchConfig

        config = RustSearchConfig(
            entity_aware=False,
            rerank=False,
            rrf_k=100,
        )
        assert config.entity_aware is False
        assert config.rerank is False
        assert config.rrf_k == 100


class TestRAGConfig:
    """Test main RAGConfig class."""

    def test_default_creation(self):
        """Test default RAGConfig creation."""
        from omni.rag.config import (
            RAGConfig,
            DocumentParsingConfig,
            MultimodalConfig,
            KnowledgeGraphConfig,
            RustSearchConfig,
        )

        config = RAGConfig()
        assert config.enabled is True
        assert isinstance(config.document_parsing, DocumentParsingConfig)
        assert isinstance(config.multimodal, MultimodalConfig)
        assert isinstance(config.knowledge_graph, KnowledgeGraphConfig)
        assert isinstance(config.rust_search, RustSearchConfig)

    def test_from_dict(self):
        """Test RAGConfig creation from dictionary."""
        from omni.rag.config import RAGConfig

        data = {
            "enabled": False,
            "document_parsing": {"enabled": True, "parser": "mineru"},
            "multimodal": {"enabled": True, "vision_model": "local-vlm"},
        }
        config = RAGConfig.from_dict(data)
        assert config.enabled is False
        assert config.document_parsing.enabled is True
        assert config.document_parsing.parser == "mineru"
        assert config.multimodal.enabled is True
        assert config.multimodal.vision_model == "local-vlm"

    def test_is_enabled(self):
        """Test is_enabled method."""
        from omni.rag.config import RAGConfig

        config = RAGConfig()
        assert config.is_enabled("document_parsing") is True
        assert config.is_enabled("multimodal") is False
        assert config.is_enabled("knowledge_graph") is True
        assert config.is_enabled("rust_search") is True
        assert config.is_enabled("nonexistent") is False

        # Master switch
        config.enabled = False
        assert config.is_enabled("document_parsing") is False


class TestRAGConfigFunctions:
    """Test module-level configuration functions."""

    def test_get_parser_when_enabled(self):
        """Test get_parser when document parsing is enabled."""
        from omni.rag.config import get_parser, reload_rag_config

        reload_rag_config()  # Reset cached config
        parser = get_parser()
        assert parser is not None
        assert parser in ["docling", "mineru", "auto"]

    def test_get_parser_with_override(self):
        """Test get_parser with custom parser name."""
        from omni.rag.config import get_parser, reload_rag_config

        reload_rag_config()
        parser = get_parser("mineru")
        assert parser == "mineru"

    def test_is_knowledge_graph_enabled(self):
        """Test is_knowledge_graph_enabled function."""
        from omni.rag.config import is_knowledge_graph_enabled, reload_rag_config

        reload_rag_config()
        assert is_knowledge_graph_enabled() is True

    def test_is_multimodal_enabled(self):
        """Test is_multimodal_enabled function."""
        from omni.rag.config import is_multimodal_enabled, reload_rag_config

        reload_rag_config()
        assert is_multimodal_enabled() is False  # Default is disabled

    def test_reload_rag_config(self):
        """Test reload_rag_config function."""
        from omni.rag.config import get_rag_config, reload_rag_config

        config1 = get_rag_config()
        config2 = reload_rag_config()
        assert config2 is not None
        # Both should be equal in value
        assert config1.enabled == config2.enabled
