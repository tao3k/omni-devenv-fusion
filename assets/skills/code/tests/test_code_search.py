"""
Tests for code.code_search command (formerly code).

Tests cover:
- Unified code search command (AST + Vector + Grep)
- Graph-based search orchestration
- Result formatting

Usage:
    python -m pytest packages/python/core/tests/units/code/test_code_search.py -v
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCodeSearchCommand:
    """Tests for the code_search command."""

    @pytest.fixture
    def skill_loader(self):
        """Create a skill loader for code."""
        from omni.core.skills.tools_loader import create_tools_loader
        from omni.foundation.config.skills import SKILLS_DIR

        scripts_path = SKILLS_DIR() / "code" / "scripts"
        loader = create_tools_loader(scripts_path, "code")
        loader.load_all()
        return loader

    def test_code_search_command_exists(self, skill_loader):
        """Test that code_search command is registered."""
        assert "code.code_search" in skill_loader.commands

    def test_code_search_is_async(self, skill_loader):
        """Test that code_search is an async function."""
        code_search = skill_loader.commands["code.code_search"]
        assert asyncio.iscoroutinefunction(code_search)

    @pytest.mark.asyncio
    async def test_code_search_returns_xml_format(self, skill_loader):
        """Test that code_search returns XML-formatted output."""
        code_search = skill_loader.commands["code.code_search"]
        result = await code_search("def test_function")

        # Result should be a string
        assert isinstance(result, str)

        # Result should contain XML-like tags
        assert "<" in result and ">" in result

    @pytest.mark.asyncio
    async def test_code_search_class_query(self, skill_loader):
        """Test code_search with class query."""
        code_search = skill_loader.commands["code.code_search"]

        # Test with a simple class query
        result = await code_search("class TestClass")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_code_search_function_query(self, skill_loader):
        """Test code_search with function query."""
        code_search = skill_loader.commands["code.code_search"]

        # Test with a function query
        result = await code_search("def hello_world")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_code_search_with_session_id(self, skill_loader):
        """Test code_search with custom session_id."""
        code_search = skill_loader.commands["code.code_search"]

        result = await code_search("def test", session_id="test_session_123")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_code_search_empty_query(self, skill_loader):
        """Test code_search with empty query."""
        code_search = skill_loader.commands["code.code_search"]

        result = await code_search("")
        assert isinstance(result, str)

    def test_code_search_has_skill_config(self, skill_loader):
        """Test that code_search has proper skill config."""
        code_search = skill_loader.commands["code.code_search"]

        assert hasattr(code_search, "_is_skill_command")
        assert code_search._is_skill_command is True

        assert hasattr(code_search, "_skill_config")
        config = code_search._skill_config
        assert config["name"] == "code_search"
        assert config["category"] == "search"


class TestSearchEngines:
    """Tests for search engine wrappers."""

    def test_run_ast_search_import(self):
        """Test that AST search engine can be imported."""
        from code.scripts.search.nodes.engines import run_ast_search

        assert callable(run_ast_search)

    def test_run_grep_search_import(self):
        """Test that grep search engine can be imported."""
        from code.scripts.search.nodes.engines import run_grep_search

        assert callable(run_grep_search)

    def test_run_vector_search_import(self):
        """Test that vector search engine can be imported."""
        from code.scripts.search.nodes.engines import run_vector_search

        assert callable(run_vector_search)

    def test_extract_ast_pattern_class(self):
        """Test AST pattern extraction for class."""
        from code.scripts.search.nodes.engines import extract_ast_pattern

        result = extract_ast_pattern("Find the class User")
        assert result == "class User"

    def test_extract_ast_pattern_class(self):
        """Test AST pattern extraction for class."""
        from code.scripts.search.nodes.engines import extract_ast_pattern

        result = extract_ast_pattern("Find class User")
        assert "class" in result and "User" in result

    def test_extract_ast_pattern_fallback(self):
        """Test AST pattern fallback for simple patterns."""
        from code.scripts.search.nodes.engines import extract_ast_pattern

        # Simple patterns like "def hello" should be returned as-is
        result = extract_ast_pattern("def hello")
        assert "def" in result or "hello" in result


class TestSearchGraph:
    """Tests for search graph components."""

    def test_search_graph_state_import(self):
        """Test that SearchGraphState can be imported."""
        from code.scripts.search.state import SearchGraphState

        assert SearchGraphState is not None

    def test_search_graph_state_creation(self):
        """Test SearchGraphState creation."""
        from code.scripts.search.state import SearchGraphState

        state = SearchGraphState(query="test query")
        assert state["query"] == "test query"

    def test_create_search_graph(self):
        """Test that search graph can be created."""
        from code.scripts.search.graph import create_search_graph

        graph = create_search_graph()
        assert graph is not None


class TestSearchNodes:
    """Tests for search graph nodes."""

    def test_node_run_ast_search(self):
        """Test AST search node."""
        from code.scripts.search.nodes.engines import (
            node_run_ast_search,
        )
        from code.scripts.search.state import SearchGraphState

        state = SearchGraphState(query="class Test")
        result = node_run_ast_search(state)
        assert "raw_results" in result
        assert isinstance(result["raw_results"], list)

    def test_node_run_grep_search(self):
        """Test grep search node."""
        from code.scripts.search.nodes.engines import (
            node_run_grep_search,
        )
        from code.scripts.search.state import SearchGraphState

        state = SearchGraphState(query="def test")
        result = node_run_grep_search(state)
        assert "raw_results" in result

    def test_node_run_vector_search(self):
        """Test vector search node."""
        from code.scripts.search.nodes.engines import (
            node_run_vector_search,
        )
        from code.scripts.search.state import SearchGraphState

        state = SearchGraphState(query="test query")
        result = node_run_vector_search(state)
        assert "raw_results" in result


class TestSearchClassifier:
    """Tests for search classifier."""

    def test_classifier_import(self):
        """Test that classifier can be imported."""
        from code.scripts.search.nodes import classifier

        assert classifier is not None


class TestSearchFormatter:
    """Tests for search result formatter."""

    def test_formatter_import(self):
        """Test that formatter can be imported."""
        from code.scripts.search.nodes import formatter

        assert formatter is not None
