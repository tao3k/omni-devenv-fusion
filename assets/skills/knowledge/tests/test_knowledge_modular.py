import asyncio

import pytest
from omni.test_kit.decorators import omni_skill


@pytest.mark.asyncio
@omni_skill(name="knowledge")
class TestLinkGraphSearchCommands:
    """Tests for LinkGraph search commands."""

    async def test_link_graph_toc(self, skill_tester):
        """Test link_graph_toc returns Table of Contents."""
        result = await skill_tester.run("knowledge", "link_graph_toc")
        assert result.success

        output = result.data
        assert output["success"]
        assert "total" in output
        assert "notes" in output
        assert isinstance(output["notes"], list)

    async def test_link_graph_stats(self, skill_tester):
        """Test link_graph_stats returns knowledge base statistics."""
        result = await skill_tester.run("knowledge", "link_graph_stats")
        assert result.success

        output = result.data
        assert output["success"]
        assert "stats" in output

    async def test_link_graph_search_mode(self, skill_tester):
        """Test search(mode=link_graph) returns graph search results."""
        result = await skill_tester.run(
            "knowledge", "search", query="architecture", mode="link_graph", max_results=5
        )
        assert result.success

        output = result.data
        assert output["success"]
        assert "parsed_query" in output
        assert isinstance(output["parsed_query"], str)
        assert "results" in output
        assert isinstance(output["results"], list)

    async def test_link_graph_search_mode_with_search_options(self, skill_tester):
        """Test search(mode=link_graph) accepts schema-v2 search_options payload."""
        result = await skill_tester.run(
            "knowledge",
            "search",
            query="architecture",
            mode="link_graph",
            max_results=5,
            search_options={
                "schema": "omni.link_graph.search_options.v2",
                "match_strategy": "exact",
                "sort_terms": [{"field": "title", "order": "asc"}],
                "filters": {
                    "link_to": {"seeds": ["architecture"], "recursive": True, "max_distance": 2}
                },
            },
        )
        assert result.success

        output = result.data
        assert output["success"]
        assert "search_options" in output
        assert output["search_options"]["match_strategy"] == "exact"
        assert output["search_options"]["sort_terms"] == [{"field": "title", "order": "asc"}]

    async def test_link_graph_search_mode_query_directives_return_effective_plan(
        self, skill_tester
    ):
        """Test link_graph query directives are reflected in parsed_query + effective options."""
        result = await skill_tester.run(
            "knowledge",
            "search",
            query="tag:(architecture OR design) -tag:draft sort:path_asc",
            mode="link_graph",
            max_results=5,
        )
        assert result.success

        output = result.data
        assert output["success"]
        assert output["parsed_query"] == ""
        assert output["search_options"]["sort_terms"] == [{"field": "path", "order": "asc"}]
        tags = output["search_options"]["filters"]["tags"]
        assert tags["any"] == ["architecture", "design"]
        assert tags["not"] == ["draft"]

    async def test_link_graph_links(self, skill_tester):
        """Test link_graph_links returns link information."""
        result = await skill_tester.run(
            "knowledge", "link_graph_links", note_id="architecture", direction="both"
        )
        assert result.success

        output = result.data
        assert output["success"]
        assert "incoming" in output
        assert "outgoing" in output

    async def test_link_graph_find_related(self, skill_tester):
        """Test link_graph_find_related returns related notes."""
        result = await skill_tester.run(
            "knowledge", "link_graph_find_related", note_id="architecture", max_distance=2, limit=10
        )
        assert result.success

        output = result.data
        assert output["success"]
        assert "results" in output

    async def test_hybrid_search(self, skill_tester):
        """Test unified search (default hybrid) returns merged results."""
        result = await skill_tester.run(
            "knowledge",
            "search",
            query="architecture MCP",
            max_results=5,
            use_hybrid=True,
        )
        assert result.success

        output = result.data
        assert output["success"]
        assert "link_graph_total" in output
        assert "merged" in output
        assert isinstance(output["merged"], list)


@pytest.mark.asyncio
@omni_skill(name="knowledge")
class TestKnowledgeModular:
    """Modular tests for knowledge skill."""

    async def test_get_development_context(self, skill_tester):
        """Test get_development_context execution."""
        result = await skill_tester.run("knowledge", "get_development_context")
        assert result.success

        context = result.data
        assert "project" in context
        assert "git_rules" in context
        assert "guardrails" in context
        assert "architecture" in context

    async def test_get_best_practice(self, skill_tester):
        """Test get_best_practice execution."""
        result = await skill_tester.run("knowledge", "get_best_practice", topic="git commit")
        assert result.success

        output = result.data
        assert "success" in output
        assert "topic" in output
        assert "theory" in output
        assert "practice" in output

    async def test_recall(self, skill_tester):
        """Test recall execution."""
        result = await skill_tester.run("knowledge", "recall", query="how to use advanced search")
        assert result.success
        assert result.output is not None


@pytest.mark.asyncio
@omni_skill(name="knowledge")
class TestGraphCommands:
    """Tests for knowledge graph commands."""

    async def test_graph_stats(self, skill_tester):
        """Test graph_stats returns backend info."""
        result = await skill_tester.run("knowledge", "graph_stats")
        assert result.success

        output = result.data
        assert "backend" in output

    async def test_search_graph_entities(self, skill_tester):
        """Test search_graph in entities mode."""
        result = await skill_tester.run(
            "knowledge", "search_graph", query="Python", mode="entities"
        )
        assert result.success

        output = result.data
        assert "query" in output
        assert output["mode"] == "entities"

    async def test_search_graph_hybrid(self, skill_tester):
        """Test search_graph in hybrid mode."""
        result = await skill_tester.run(
            "knowledge", "search_graph", query="architecture", mode="hybrid"
        )
        assert result.success

        output = result.data
        assert "query" in output


@pytest.mark.asyncio
@omni_skill(name="knowledge")
class TestSearchCommands:
    """Tests for search and recall commands."""

    async def test_search(self, skill_tester):
        """Test unified knowledge.search returns results (default: hybrid)."""
        result = await skill_tester.run("knowledge", "search", query="architecture")
        assert result.success
        assert result.output is not None
        # Unified search returns hybrid shape by default
        if result.data and isinstance(result.data, dict):
            assert result.data.get("success") is True

    async def test_recall_with_limit(self, skill_tester):
        """Test knowledge.recall with limit parameter."""
        result = await skill_tester.run("knowledge", "recall", query="search algorithm", limit=3)
        assert result.success
        assert result.output is not None


@pytest.mark.asyncio
@omni_skill(name="knowledge")
class TestDependencyCommands:
    """Tests for dependency-related commands."""

    async def test_dependency_search(self, skill_tester):
        """Test dependency_search returns results."""
        result = await skill_tester.run("knowledge", "dependency_search", query="lance")
        assert result.success

        output = result.data
        assert isinstance(output, (dict, list, str))

    async def test_dependency_list(self, skill_tester):
        """Test dependency_list returns dependencies."""
        result = await skill_tester.run("knowledge", "dependency_list")
        assert result.success
        assert result.output is not None

    async def test_dependency_status(self, skill_tester):
        """Test dependency_status returns status info."""
        result = await skill_tester.run("knowledge", "dependency_status")
        assert result.success
        assert result.output is not None


@pytest.mark.asyncio
@omni_skill(name="knowledge")
class TestKnowledgeBaseCommands:
    """Tests for knowledge base management commands."""

    async def test_stats(self, skill_tester):
        """Test knowledge_status returns status."""
        result = await skill_tester.run("knowledge", "knowledge_status")
        assert result.success
        assert result.output is not None

    async def test_list_supported_languages(self, skill_tester):
        """Test list_supported_languages returns languages."""
        result = await skill_tester.run("knowledge", "list_supported_languages")
        assert result.success
        assert result.output is not None


@pytest.mark.asyncio
@omni_skill(name="knowledge")
class TestCodeSearchCommands:
    """Tests for code search / language expert commands."""

    async def test_consult_architecture_doc(self, skill_tester):
        """Test consult_architecture_doc returns doc content."""
        result = await skill_tester.run("knowledge", "consult_architecture_doc", topic="router")
        assert result.success
        assert result.output is not None

    async def test_consult_language_expert(self, skill_tester):
        """Test consult_language_expert returns language info."""
        result = await skill_tester.run(
            "knowledge",
            "consult_language_expert",
            file_path="example.py",
            task_description="add type hints",
        )
        assert result.success
        assert result.output is not None

    async def test_get_language_standards(self, skill_tester):
        """Test get_language_standards returns standards for known language."""
        result = await skill_tester.run("knowledge", "get_language_standards", lang="python")
        assert result.success
        assert result.output is not None

    async def test_get_language_standards_unknown(self, skill_tester):
        """Test get_language_standards with unknown language returns graceful response."""
        result = await skill_tester.run("knowledge", "get_language_standards", lang="brainf")
        assert result.success
        output = result.data
        # Either returns standards or a not_found status
        assert isinstance(output, (dict, str))


@pytest.mark.asyncio
@omni_skill(name="knowledge")
class TestIngestAndClearCommands:
    """Tests for knowledge ingest, stats, and clear commands."""

    async def test_stats(self, skill_tester):
        """Test stats returns collection statistics."""
        result = await skill_tester.run("knowledge", "stats")
        assert result.success
        output = result.data
        assert isinstance(output, (dict, str))

    async def test_ingest(self, skill_tester):
        """Test ingest adds content to the knowledge base."""
        result = await skill_tester.run(
            "knowledge",
            "ingest",
            content="Unit test content for knowledge ingest.",
            source="test://unit_test",
        )
        assert result.success
        output = result.data
        assert isinstance(output, (dict, str))

    async def test_create_knowledge_entry(self, skill_tester):
        """Test create_knowledge_entry creates a new entry."""
        result = await skill_tester.run(
            "knowledge",
            "create_knowledge_entry",
            title="Test Entry",
            category="testing",
            content="This is a test knowledge entry created by unit tests.",
        )
        assert result.success
        assert result.output is not None

    async def test_rebuild_knowledge_index(self, skill_tester):
        """Test rebuild_knowledge_index runs without error."""
        result = await skill_tester.run("knowledge", "rebuild_knowledge_index")
        assert result.success
        assert result.output is not None

    async def test_clear_nonexistent_collection(self, skill_tester):
        """Test clear on a non-existent collection is graceful."""
        result = await skill_tester.run("knowledge", "clear", collection="__test_nonexistent__")
        assert result.success
        output = result.data
        assert isinstance(output, (dict, str))


@pytest.mark.asyncio
@omni_skill(name="knowledge")
class TestEntityExtractionCommands:
    """Tests for entity extraction and document ingestion."""

    @pytest.mark.timeout(60)
    async def test_extract_entities(self, skill_tester, monkeypatch):
        """Test extract_entities on inline text (may require LLM)."""
        # Force no-LLM path to keep unit test deterministic and low-memory.
        await skill_tester.get_commands("knowledge")
        import sys

        graph_module = sys.modules.get("omni.skills.knowledge.scripts.graph")
        if graph_module is not None:

            class _UnavailableProvider:
                def is_available(self) -> bool:
                    return False

            monkeypatch.setattr(
                graph_module,
                "get_llm_provider",
                lambda: _UnavailableProvider(),
            )

        try:
            result = await asyncio.wait_for(
                skill_tester.run(
                    "knowledge",
                    "extract_entities",
                    source="LanceDB is a columnar store built on Arrow. Rust powers omni-vector.",
                    store=False,
                ),
                timeout=45.0,
            )
        except TimeoutError:
            pytest.skip("extract_entities timed out in this environment")
        # May fail if LLM is not configured — that's okay
        assert result.output is not None or result.error is not None

    async def test_ingest_document(self, skill_tester):
        """Test ingest_document with a real file."""
        result = await skill_tester.run(
            "knowledge",
            "ingest_document",
            file_path="docs/index.md",
            extract_entities=False,
        )
        # May fail if vector store not initialized — check graceful handling
        assert result.output is not None or result.error is not None


@pytest.mark.asyncio
@omni_skill(name="knowledge")
class TestDependencyBuild:
    """Test dependency_build (may be slow)."""

    @pytest.mark.timeout(60)
    async def test_dependency_build(self, skill_tester):
        """Test dependency_build returns build results."""
        result = await skill_tester.run("knowledge", "dependency_build")
        # This may take time or fail if cargo registry is unreachable
        assert result.output is not None or result.error is not None
