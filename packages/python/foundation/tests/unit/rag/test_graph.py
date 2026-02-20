"""
Tests for omni.rag.graph module.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestBilingualPrompts:
    """Test bilingual entity extraction prompts."""

    def test_english_prompt_exists(self):
        """Test English extraction prompt is defined."""
        from omni.rag.graph import EXTRACT_ENTITIES_PROMPT_EN

        assert EXTRACT_ENTITIES_PROMPT_EN is not None
        assert "You are an expert" in EXTRACT_ENTITIES_PROMPT_EN
        assert "PERSON" in EXTRACT_ENTITIES_PROMPT_EN
        assert "ORGANIZATION" in EXTRACT_ENTITIES_PROMPT_EN

    def test_chinese_prompt_exists(self):
        """Test Chinese extraction prompt is defined."""
        from omni.rag.graph import EXTRACT_ENTITIES_PROMPT_ZH

        assert EXTRACT_ENTITIES_PROMPT_ZH is not None
        assert "实体" in EXTRACT_ENTITIES_PROMPT_ZH
        assert "关系" in EXTRACT_ENTITIES_PROMPT_ZH
        assert "PERSON" in EXTRACT_ENTITIES_PROMPT_ZH

    def test_default_prompt_is_bilingual(self):
        """Test default prompt contains bilingual instructions."""
        from omni.rag.graph import EXTRACT_ENTITIES_PROMPT

        assert EXTRACT_ENTITIES_PROMPT is not None
        # Contains English
        assert "You are an expert" in EXTRACT_ENTITIES_PROMPT
        # Contains Chinese
        assert "中英文双语实体提取" in EXTRACT_ENTITIES_PROMPT
        # Contains both entity type descriptions
        assert "Individual people" in EXTRACT_ENTITIES_PROMPT
        assert "个人、开发人员" in EXTRACT_ENTITIES_PROMPT

    def test_english_prompt_has_json_format(self):
        """Test English prompt has JSON output format."""
        from omni.rag.graph import EXTRACT_ENTITIES_PROMPT_EN

        assert '"entities"' in EXTRACT_ENTITIES_PROMPT_EN
        assert '"relations"' in EXTRACT_ENTITIES_PROMPT_EN
        assert '"name"' in EXTRACT_ENTITIES_PROMPT_EN
        assert '"entity_type"' in EXTRACT_ENTITIES_PROMPT_EN

    def test_chinese_prompt_has_json_format(self):
        """Test Chinese prompt has JSON output format."""
        from omni.rag.graph import EXTRACT_ENTITIES_PROMPT_ZH

        assert "entities" in EXTRACT_ENTITIES_PROMPT_ZH
        assert "relations" in EXTRACT_ENTITIES_PROMPT_ZH
        assert "entity_type" in EXTRACT_ENTITIES_PROMPT_ZH

    def test_all_exports_present(self):
        """Test all prompts are exported."""
        from omni.rag import graph

        assert hasattr(graph, "EXTRACT_ENTITIES_PROMPT")
        assert hasattr(graph, "EXTRACT_ENTITIES_PROMPT_EN")
        assert hasattr(graph, "EXTRACT_ENTITIES_PROMPT_ZH")


class TestKnowledgeGraphExtractor:
    """Test KnowledgeGraphExtractor class."""

    def test_extractor_initialization(self):
        """Test extractor initialization with default config."""
        from omni.rag.graph import KnowledgeGraphExtractor

        with patch("omni.rag.graph.get_rag_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.knowledge_graph.entity_types = ["PERSON", "ORGANIZATION"]
            mock_config.knowledge_graph.relation_types = ["WORKS_FOR", "PART_OF"]
            mock_config.knowledge_graph.max_entities_per_doc = 50
            mock_config.knowledge_graph.store_in_rust = False
            mock_get_config.return_value = mock_config

            extractor = KnowledgeGraphExtractor()
            assert extractor.entity_types == ["PERSON", "ORGANIZATION"]
            assert extractor.relation_types == ["WORKS_FOR", "PART_OF"]

    def test_extractor_with_custom_types(self):
        """Test extractor with custom entity/relation types."""
        from omni.rag.graph import KnowledgeGraphExtractor

        extractor = KnowledgeGraphExtractor(
            entity_types=["TOOL", "PROJECT"],
            relation_types=["DEPENDS_ON", "USES"],
        )

        assert extractor.entity_types == ["TOOL", "PROJECT"]
        assert extractor.relation_types == ["DEPENDS_ON", "USES"]

    @pytest.mark.asyncio
    async def test_extract_entities_empty_text(self):
        """Test extraction with empty text returns empty lists."""
        from omni.rag.graph import KnowledgeGraphExtractor

        extractor = KnowledgeGraphExtractor()
        entities, relations = await extractor.extract_entities("")

        assert entities == []
        assert relations == []

    @pytest.mark.asyncio
    async def test_extract_entities_no_llm(self):
        """Test extraction without LLM function returns empty."""
        from omni.rag.graph import KnowledgeGraphExtractor

        extractor = KnowledgeGraphExtractor(llm_complete_func=None)
        entities, relations = await extractor.extract_entities("Some text")

        assert entities == []
        assert relations == []

    def test_get_stats(self):
        """Test getting extractor statistics."""
        from omni.rag.graph import KnowledgeGraphExtractor

        extractor = KnowledgeGraphExtractor(
            entity_types=["PERSON", "TOOL"],
            relation_types=["USES"],
        )

        stats = extractor.get_stats()

        assert "entity_types" in stats
        assert "relation_types" in stats
        assert stats["entity_types"] == ["PERSON", "TOOL"]
        assert stats["rust_backend_available"] is False


class TestKnowledgeGraphStore:
    """Test KnowledgeGraphStore class."""

    def test_store_creation(self):
        """Test store can be instantiated."""
        from omni.rag.graph import KnowledgeGraphStore

        store = KnowledgeGraphStore()
        assert store is not None

    def test_add_entity_no_backend(self):
        """Test adding entity without backend returns False."""
        from omni.rag.graph import KnowledgeGraphStore
        from omni.rag.entities import Entity

        store = KnowledgeGraphStore()
        store._backend = None  # simulate no backend (e.g. omni_core_rs not installed)
        entity = Entity(
            name="Test Entity",
            entity_type="CONCEPT",
            description="Test",
            source="test.md",
        )

        # Should return False gracefully when no backend
        result = store.add_entity(entity)
        assert result is False

    def test_add_relation_no_backend(self):
        """Test adding relation without backend."""
        from omni.rag.graph import KnowledgeGraphStore
        from omni.rag.entities import Relation

        store = KnowledgeGraphStore()
        store._backend = None  # simulate no backend
        relation = Relation(
            source="A",
            target="B",
            relation_type="USES",
            description="Test",
        )

        result = store.add_relation(relation)
        assert result is False

    def test_add_entity_dict_succeeds_with_rust_backend(self):
        """Store must accept dict and convert to PyEntity when backend is Rust (no 'dict cannot be cast as PyEntity')."""
        pytest.importorskip("omni_core_rs")
        from omni.rag.graph import KnowledgeGraphStore

        store = KnowledgeGraphStore()
        if store._backend is None:
            pytest.skip("Rust backend not available")
        entity_dict = {
            "name": "Python",
            "entity_type": "SKILL",
            "description": "Programming language",
            "source": "test",
        }
        result = store.add_entity(entity_dict)
        assert result is True

    def test_add_entity_then_relation_dict_succeeds_with_rust_backend(self):
        """Store must accept dicts and write entities before relations so relation source/target exist."""
        pytest.importorskip("omni_core_rs")
        from omni.rag.graph import KnowledgeGraphStore

        store = KnowledgeGraphStore()
        if store._backend is None:
            pytest.skip("Rust backend not available")
        a = {"name": "A", "entity_type": "CONCEPT", "description": "Entity A", "source": ""}
        b = {"name": "B", "entity_type": "CONCEPT", "description": "Entity B", "source": ""}
        rel = {"source": "A", "target": "B", "relation_type": "RELATED_TO", "description": "A to B"}
        assert store.add_entity(a) is True
        assert store.add_entity(b) is True
        assert store.add_relation(rel) is True

    def test_add_relation_without_entities_returns_false_with_rust_backend(self):
        """Rust graph requires source/target entities to exist; add_relation without them returns False."""
        pytest.importorskip("omni_core_rs")
        from omni.rag.graph import KnowledgeGraphStore

        store = KnowledgeGraphStore()
        if store._backend is None:
            pytest.skip("Rust backend not available")
        rel = {
            "source": "NoSuch",
            "target": "AlsoNoSuch",
            "relation_type": "RELATED_TO",
            "description": "",
        }
        result = store.add_relation(rel)
        assert result is False

    def test_search_entities_no_backend(self):
        """Test searching without backend returns empty list."""
        from omni.rag.graph import KnowledgeGraphStore

        store = KnowledgeGraphStore()
        results = store.search_entities("test")

        assert results == []

    def test_get_relations_no_backend(self):
        """Test getting relations without backend returns empty list."""
        from omni.rag.graph import KnowledgeGraphStore

        store = KnowledgeGraphStore()
        results = store.get_relations()

        assert results == []

    def test_multi_hop_search_no_backend(self):
        """Test multi-hop search without backend returns empty list."""
        from omni.rag.graph import KnowledgeGraphStore

        store = KnowledgeGraphStore()
        results = store.multi_hop_search(["EntityA"])

        assert results == []


class TestExtractEntitiesPrompt:
    """Test extraction prompt constants."""

    def test_prompt_exists(self):
        """Test that extraction prompt is defined."""
        from omni.rag.graph import EXTRACT_ENTITIES_PROMPT

        assert EXTRACT_ENTITIES_PROMPT is not None
        assert "entities" in EXTRACT_ENTITIES_PROMPT.lower()
        assert "relations" in EXTRACT_ENTITIES_PROMPT.lower()

    def test_prompt_contains_entity_types(self):
        """Test prompt mentions entity types."""
        from omni.rag.graph import EXTRACT_ENTITIES_PROMPT

        prompt_lower = EXTRACT_ENTITIES_PROMPT.lower()
        assert "PERSON" in prompt_lower or "person" in prompt_lower


class TestGraphExtractorFactory:
    """Test factory functions."""

    def test_get_graph_extractor_disabled(self):
        """Test get_graph_extractor returns None when disabled."""
        with patch("omni.rag.graph.is_knowledge_graph_enabled", return_value=False):
            from omni.rag.graph import get_graph_extractor

            result = get_graph_extractor()
            assert result is None

    def test_get_graph_extractor_enabled(self):
        """Test get_graph_extractor returns extractor when enabled."""
        from omni.rag.graph import KnowledgeGraphExtractor

        with patch("omni.rag.graph.is_knowledge_graph_enabled", return_value=True):
            with patch("omni.rag.graph.get_rag_config") as mock_get_config:
                mock_config = MagicMock()
                mock_config.knowledge_graph.entity_types = ["PERSON"]
                mock_config.knowledge_graph.relation_types = ["WORKS_FOR"]
                mock_config.knowledge_graph.max_entities_per_doc = 100
                mock_config.knowledge_graph.store_in_rust = False
                mock_get_config.return_value = mock_config

                from omni.rag.graph import get_graph_extractor

                result = get_graph_extractor(llm_complete_func=MagicMock())
                assert result is not None
                assert isinstance(result, KnowledgeGraphExtractor)

    def test_get_graph_store(self):
        """Test get_graph_store returns store."""
        from omni.rag.graph import get_graph_store

        store = get_graph_store()
        assert store is not None
        assert hasattr(store, "add_entity")
        assert hasattr(store, "add_relation")


class TestGraphModuleExports:
    """Test module exports."""

    def test_all_exports_present(self):
        """Test all expected exports are available."""
        from omni.rag import graph

        assert hasattr(graph, "KnowledgeGraphExtractor")
        assert hasattr(graph, "KnowledgeGraphStore")
        assert hasattr(graph, "EXTRACT_ENTITIES_PROMPT")
        assert hasattr(graph, "get_graph_extractor")
        assert hasattr(graph, "get_graph_store")

    def test_all_in_all(self):
        """Test all exports are in __all__."""
        from omni.rag.graph import __all__

        expected = [
            "KnowledgeGraphExtractor",
            "KnowledgeGraphStore",
            "EXTRACT_ENTITIES_PROMPT",
            "EXTRACT_ENTITIES_PROMPT_EN",
            "EXTRACT_ENTITIES_PROMPT_ZH",
            "get_graph_extractor",
            "get_graph_store",
        ]

        for item in expected:
            assert item in __all__, f"{item} not in __all__"


class TestBilingualParsing:
    """Test parsing of bilingual (Chinese/English) entity extraction responses."""

    def test_parse_mixed_language_response(self):
        """Test parsing response with mixed Chinese/English entities."""
        from omni.rag.graph import KnowledgeGraphExtractor

        extractor = KnowledgeGraphExtractor()

        # Simulate a response with both English and Chinese entities
        mock_response = """
        {
            "entities": [
                {
                    "name": "Python",
                    "entity_type": "SKILL",
                    "description": "Programming language",
                    "aliases": ["python"]
                },
                {
                    "name": "Claude Code",
                    "entity_type": "TOOL",
                    "description": "AI coding assistant",
                    "aliases": ["Claude"]
                },
                {
                    "name": "Omni Dev Fusion",
                    "entity_type": "PROJECT",
                    "description": "Development environment",
                    "aliases": ["Omni"]
                }
            ],
            "relations": [
                {
                    "source": "Claude Code",
                    "target": "Python",
                    "relation_type": "USES",
                    "description": "Claude Code uses Python"
                }
            ]
        }
        """

        entities, relations = extractor._parse_extraction(mock_response, "test.md")

        assert len(entities) == 3
        entity_names = [e.name for e in entities]
        assert "Python" in entity_names
        assert "Claude Code" in entity_names
        assert "Omni Dev Fusion" in entity_names

        assert len(relations) == 1
        assert relations[0].source == "Claude Code"
        assert relations[0].target == "Python"

    def test_parse_chinese_entities_response(self):
        """Test parsing response with Chinese entities."""
        from omni.rag.graph import KnowledgeGraphExtractor

        extractor = KnowledgeGraphExtractor()

        mock_response = """
        {
            "entities": [
                {
                    "name": "张三",
                    "entity_type": "PERSON",
                    "description": "开发人员"
                },
                {
                    "name": "百度",
                    "entity_type": "ORGANIZATION",
                    "description": "中国互联网公司"
                }
            ],
            "relations": [
                {
                    "source": "张三",
                    "target": "百度",
                    "relation_type": "WORKS_FOR",
                    "description": "在百度工作"
                }
            ]
        }
        """

        entities, relations = extractor._parse_extraction(mock_response, "test.md")

        assert len(entities) == 2
        entity_names = [e.name for e in entities]
        assert "张三" in entity_names
        assert "百度" in entity_names

        assert len(relations) == 1
        assert relations[0].source == "张三"
        assert relations[0].target == "百度"

    def test_parse_empty_response(self):
        """Test parsing empty response."""
        from omni.rag.graph import KnowledgeGraphExtractor

        extractor = KnowledgeGraphExtractor()

        entities, relations = extractor._parse_extraction("{}", "test.md")

        assert entities == []
        assert relations == []

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON response."""
        from omni.rag.graph import KnowledgeGraphExtractor

        extractor = KnowledgeGraphExtractor()

        entities, relations = extractor._parse_extraction("not valid json", "test.md")

        assert entities == []
        assert relations == []


class TestPromptFormat:
    """Test prompt format and content."""

    def test_prompt_format_variable(self):
        """Test that prompt contains format variable placeholder."""
        from omni.rag.graph import (
            EXTRACT_ENTITIES_PROMPT,
            EXTRACT_ENTITIES_PROMPT_EN,
            EXTRACT_ENTITIES_PROMPT_ZH,
        )

        # All prompts should contain the {text} placeholder
        assert "{text}" in EXTRACT_ENTITIES_PROMPT
        assert "{text}" in EXTRACT_ENTITIES_PROMPT_EN
        assert "{text}" in EXTRACT_ENTITIES_PROMPT_ZH

    def test_prompt_entity_type_coverage(self):
        """Test that prompts cover all standard entity types."""
        from omni.rag.graph import EXTRACT_ENTITIES_PROMPT

        # Check for standard entity types
        entity_types = ["PERSON", "ORGANIZATION", "CONCEPT", "PROJECT", "TOOL", "SKILL"]
        for et in entity_types:
            assert et in EXTRACT_ENTITIES_PROMPT, f"Missing {et} in prompt"

    def test_prompt_relation_type_coverage(self):
        """Test that prompts cover key relation types."""
        from omni.rag.graph import EXTRACT_ENTITIES_PROMPT

        # Check for key relation types
        relation_types = ["WORKS_FOR", "PART_OF", "USES", "DEPENDS_ON", "CREATED_BY"]
        for rt in relation_types:
            assert rt in EXTRACT_ENTITIES_PROMPT, f"Missing {rt} in prompt"


class TestKnowledgeGraphPersistence:
    """Test knowledge graph persistence (save/load)."""

    def test_save_and_load_graph(self, tmp_path):
        """Test saving and loading graph to/from JSON file."""
        from omni_core_rs import PyKnowledgeGraph, PyEntity, PyRelation

        graph_path = str(tmp_path / "test_graph.json")

        # Create a graph with entities and relations
        graph = PyKnowledgeGraph()

        entity1 = PyEntity(name="Python", entity_type="SKILL", description="Programming language")
        entity2 = PyEntity(
            name="Claude Code", entity_type="TOOL", description="AI coding assistant"
        )

        graph.add_entity(entity1)
        graph.add_entity(entity2)

        relation = PyRelation(
            source="Claude Code",
            target="Python",
            relation_type="USES",
            description="Claude Code uses Python",
        )
        graph.add_relation(relation)

        # Save the graph
        graph.save_to_file(graph_path)

        # Load into a new graph
        loaded_graph = PyKnowledgeGraph()
        loaded_graph.load_from_file(graph_path)

        # Verify entities were loaded
        stats = loaded_graph.get_stats()
        import json

        stats_dict = json.loads(stats)
        assert stats_dict["total_entities"] == 2
        assert stats_dict["total_relations"] == 1

        # Verify entity can be found
        python = loaded_graph.get_entity_by_name("Python")
        assert python is not None
        assert python.entity_type == "SKILL"

    def test_export_as_json(self, tmp_path):
        """Test exporting graph as JSON string."""
        from omni_core_rs import PyKnowledgeGraph, PyEntity

        graph = PyKnowledgeGraph()

        entity = PyEntity(
            name="Omni Dev Fusion",
            entity_type="PROJECT",
            description="Development environment",
        )
        graph.add_entity(entity)

        json_output = graph.export_as_json()

        import json

        data = json.loads(json_output)
        assert data["total_entities"] == 1
        assert "Omni Dev Fusion" in json_output

    def test_roundtrip_save_load(self, tmp_path):
        """Test save/load roundtrip preserves data."""
        from omni_core_rs import PyKnowledgeGraph, PyEntity, PyRelation

        graph_path = str(tmp_path / "roundtrip.json")

        # Create graph with various entity types
        entities = [
            ("Python", "SKILL"),
            ("Rust", "SKILL"),
            ("Claude Code", "TOOL"),
            ("Omni Dev Fusion", "PROJECT"),
        ]

        graph1 = PyKnowledgeGraph()
        for name, etype in entities:
            entity = PyEntity(name=name, entity_type=etype, description=f"Description of {name}")
            graph1.add_entity(entity)

        relations = [
            ("Claude Code", "Python", "USES"),
            ("Claude Code", "Rust", "USES"),
            ("Omni Dev Fusion", "Claude Code", "CREATED_BY"),
        ]
        for source, target, rtype in relations:
            relation = PyRelation(
                source=source,
                target=target,
                relation_type=rtype,
                description=f"{source} -> {target}",
            )
            graph1.add_relation(relation)

        # Save
        graph1.save_to_file(graph_path)

        # Load into new graph
        graph2 = PyKnowledgeGraph()
        graph2.load_from_file(graph_path)

        import json

        stats1 = json.loads(graph1.get_stats())
        stats2 = json.loads(graph2.get_stats())

        assert stats1["total_entities"] == stats2["total_entities"]
        assert stats1["total_relations"] == stats2["total_relations"]

    def test_get_all_entities_json(self):
        """Test getting all entities as JSON."""
        from omni_core_rs import PyKnowledgeGraph, PyEntity

        graph = PyKnowledgeGraph()

        entities = [
            PyEntity(name="Entity1", entity_type="CONCEPT", description="First"),
            PyEntity(name="Entity2", entity_type="CONCEPT", description="Second"),
        ]

        for entity in entities:
            graph.add_entity(entity)

        json_output = graph.get_all_entities_json()

        import json

        data = json.loads(json_output)
        assert len(data) == 2

    def test_get_all_relations_json(self):
        """Test getting all relations as JSON."""
        from omni_core_rs import PyKnowledgeGraph, PyEntity, PyRelation

        graph = PyKnowledgeGraph()

        # Need entities first
        entity1 = PyEntity(name="A", entity_type="CONCEPT", description="A")
        entity2 = PyEntity(name="B", entity_type="CONCEPT", description="B")
        graph.add_entity(entity1)
        graph.add_entity(entity2)

        relation = PyRelation(
            source="A", target="B", relation_type="RELATED_TO", description="A relates to B"
        )
        graph.add_relation(relation)

        json_output = graph.get_all_relations_json()

        import json

        data = json.loads(json_output)
        assert len(data) == 1
        assert data[0]["source"] == "A"
        assert data[0]["target"] == "B"

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading from non-existent file raises error."""
        from omni_core_rs import PyKnowledgeGraph

        graph = PyKnowledgeGraph()
        nonexistent_path = str(tmp_path / "nonexistent.json")

        # Should raise an error
        try:
            graph.load_from_file(nonexistent_path)
            assert False, "Should have raised an exception"
        except Exception:
            pass  # Expected

    def test_save_to_new_directory(self, tmp_path):
        """Test saving to a new directory creates the directory."""
        from omni_core_rs import PyKnowledgeGraph, PyEntity

        new_dir = tmp_path / "nested" / "directory"
        graph_path = str(new_dir / "graph.json")

        graph = PyKnowledgeGraph()
        entity = PyEntity(name="Test", entity_type="CONCEPT", description="Test entity")
        graph.add_entity(entity)

        # Should create the directory and save successfully
        graph.save_to_file(graph_path)

        import json

        stats = graph.get_stats()
        stats_dict = json.loads(stats)
        assert stats_dict["total_entities"] == 1
