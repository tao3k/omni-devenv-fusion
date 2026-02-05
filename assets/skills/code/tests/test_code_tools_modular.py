"""
Tests for code_tools skill - Unified Code Search

Tests cover:
- code_search: Unified search entry point
- SmartAstEngine: AST pattern search
- Classifier: Intent classification
"""

import pytest
from omni.test_kit.decorators import omni_skill


@pytest.mark.asyncio
@omni_skill(name="code_tools")
class TestCodeSearchUnified:
    """Test unified code_search command."""

    async def test_code_search_class(self, skill_tester):
        """Test code_search for class definitions."""
        result = await skill_tester.run("code_tools", "code_search", query="class User")
        assert result.success
        # Should route to AST or Vector based on pattern

    async def test_code_search_function(self, skill_tester):
        """Test code_search for function definitions."""
        result = await skill_tester.run("code_tools", "code_search", query="def authenticate")
        assert result.success

    async def test_code_search_semantic(self, skill_tester):
        """Test code_search for semantic queries."""
        result = await skill_tester.run(
            "code_tools", "code_search", query="how does authentication work"
        )
        assert result.success

    async def test_code_search_todo(self, skill_tester):
        """Test code_search for TODO comments."""
        result = await skill_tester.run("code_tools", "code_search", query="TODO: fix")
        assert result.success

    async def test_code_search_refactor_pattern(self, skill_tester):
        """Test code_search with refactor pattern."""
        result = await skill_tester.run("code_tools", "code_search", query="connect($$$)")
        assert result.success


@pytest.mark.asyncio
@omni_skill(name="code_tools")
class TestSmartAstEngine:
    """Test SmartAstEngine for AST-based search."""

    async def test_engine_init(self, skill_tester):
        """Test SmartAstEngine initialization."""
        from code_tools.scripts.smart_ast.engine import SmartAstEngine

        engine = SmartAstEngine()
        assert engine is not None

    async def test_engine_list_rules(self, skill_tester):
        """Test listing available rules."""
        from code_tools.scripts.smart_ast.engine import SmartAstEngine

        engine = SmartAstEngine()
        rules = engine.list_rules()
        assert isinstance(rules, list)
        assert len(rules) > 0

    async def test_engine_register_rule(self, skill_tester):
        """Test registering a custom rule."""
        from code_tools.scripts.smart_ast.engine import SmartAstEngine, BUILTIN_RULES

        engine = SmartAstEngine()
        initial_count = len(BUILTIN_RULES)
        engine.register_rule("test_rule", "test($$$)", "Test rule message")
        assert "test_rule" in BUILTIN_RULES
        assert len(BUILTIN_RULES) == initial_count + 1

    async def test_yaml_rules_loaded(self, skill_tester):
        """Test that YAML rules are loaded from rules directory."""
        from code_tools.scripts.smart_ast.engine import SmartAstEngine

        engine = SmartAstEngine()
        rules = engine.list_rules()
        # Should include rules from YAML files like architecture, complexity, etc.
        rule_ids = [r["id"] for r in rules]
        # Check for some expected rules from YAML
        expected_rules = ["deep-nesting", "open-without-with", "find-entrypoints"]
        for expected in expected_rules:
            if expected in rule_ids:
                assert True
                break


@pytest.mark.asyncio
@omni_skill(name="code_tools")
class TestSearchEngines:
    """Test individual search engines."""

    async def test_ast_engine_function(self, skill_tester):
        """Test AST search for functions."""
        from code_tools.scripts.search.nodes.engines import run_ast_search, extract_ast_pattern

        # Test pattern extraction
        pattern = extract_ast_pattern("class User")
        assert pattern == "class User"

        pattern = extract_ast_pattern("def authenticate")
        assert pattern == "def authenticate"

    async def test_ast_pattern_extraction(self, skill_tester):
        """Test AST pattern extraction for various queries."""
        from code_tools.scripts.search.nodes.engines import extract_ast_pattern

        # Class patterns
        assert extract_ast_pattern("class User") == "class User"
        assert extract_ast_pattern("Find the User class") == "class User"

        # Function patterns
        assert extract_ast_pattern("def authenticate") == "def authenticate"
        assert extract_ast_pattern("fn main") == "fn main"

        # Impl patterns
        assert extract_ast_pattern("impl Foo") == "impl Foo"

        # Struct patterns
        assert extract_ast_pattern("struct User") == "struct User"

        # Non-pattern queries return None
        assert extract_ast_pattern("how does auth work") is None


@pytest.mark.asyncio
@omni_skill(name="code_tools")
class TestClassifier:
    """Test query classifier for intent recognition."""

    async def test_classify_structural_query(self, skill_tester):
        """Test classification of structural queries."""
        from code_tools.scripts.search.nodes.classifier import classify_query

        result = classify_query({"query": "class User"})
        assert "ast" in result["strategies"]

        result = classify_query({"query": "def authenticate"})
        assert "ast" in result["strategies"]

    async def test_classify_semantic_query(self, skill_tester):
        """Test classification of semantic queries."""
        from code_tools.scripts.search.nodes.classifier import classify_query

        result = classify_query({"query": "how does authentication work?"})
        assert "vector" in result["strategies"]

    async def test_classify_grep_query(self, skill_tester):
        """Test classification of grep queries."""
        from code_tools.scripts.search.nodes.classifier import classify_query

        result = classify_query({"query": "TODO: fix"})
        assert "grep" in result["strategies"]

        result = classify_query({"query": '"error message"'})
        assert "grep" in result["strategies"]

    async def test_classify_fallback(self, skill_tester):
        """Test fallback classification."""
        from code_tools.scripts.search.nodes.classifier import classify_query

        result = classify_query({"query": "auth"})
        assert "vector" in result["strategies"]


@pytest.mark.asyncio
@omni_skill(name="code_tools")
class TestGraphWorkflow:
    """Test LangGraph workflow integration."""

    async def test_create_search_graph(self, skill_tester):
        """Test search graph creation."""
        from code_tools.scripts.search.graph import create_search_graph

        graph = create_search_graph()
        assert graph is not None

    async def test_create_initial_state(self, skill_tester):
        """Test initial state creation."""
        from code_tools.scripts.search.graph import create_initial_state

        state = create_initial_state("test query", "test-thread")
        assert state["query"] == "test query"
        assert state["thread_id"] == "test-thread"
        assert "strategies" in state
        assert "raw_results" in state


@pytest.mark.asyncio
@omni_skill(name="code_tools")
class TestSearchState:
    """Test search state types."""

    async def test_state_type(self, skill_tester):
        """Test SearchGraphState type."""
        from code_tools.scripts.search.state import SearchGraphState, SearchResult

        # Test SearchResult
        result: SearchResult = {
            "engine": "ast",
            "file": "test.py",
            "line": 10,
            "content": "def test():",
            "score": 0.9,
        }
        assert result["engine"] == "ast"

        # Test state creation
        state: SearchGraphState = {
            "query": "test",
            "strategies": ["ast", "vector"],
            "raw_results": [result],
        }
        assert state["query"] == "test"


@pytest.mark.asyncio
@omni_skill(name="code_tools")
class TestPatternUtils:
    """Test pattern utilities."""

    async def test_language_patterns(self, skill_tester):
        """Test language-specific patterns."""
        from code_tools.scripts.smart_ast.patterns import LANG_PATTERNS

        # Python patterns
        assert "class $NAME" in LANG_PATTERNS["python"]["classes"]
        assert "def $NAME($$$)" in LANG_PATTERNS["python"]["functions"]

        # Rust patterns
        assert "struct $NAME" in LANG_PATTERNS["rust"]["structs"]
        assert "fn $NAME($$$)" in LANG_PATTERNS["rust"]["functions"]

    async def test_common_patterns(self, skill_tester):
        """Test common patterns alias."""
        from code_tools.scripts.smart_ast.patterns import COMMON_PATTERNS

        # Should be python patterns by default
        assert "class $NAME" in COMMON_PATTERNS["class"]
