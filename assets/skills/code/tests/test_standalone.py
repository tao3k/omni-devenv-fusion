"""
Standalone tests for code_tools AST search components.

Usage:
    pytest assets/skills/code_tools/tests/test_standalone.py -v

Or using test-kit helpers:
    from omni.test_kit.fixtures.ast import classify_query_helper, extract_ast_pattern_helper
"""

import pytest


class TestSmartAstEngine:
    """Test SmartAstEngine initialization and rules."""

    def test_engine_init(self):
        """Test SmartAstEngine initialization."""
        from code_tools.scripts.smart_ast.engine import SmartAstEngine

        engine = SmartAstEngine()
        assert engine is not None

    def test_list_rules(self):
        """Test listing available rules."""
        from code_tools.scripts.smart_ast.engine import SmartAstEngine

        engine = SmartAstEngine()
        rules = engine.list_rules()
        assert isinstance(rules, list)
        assert len(rules) > 0

    def test_register_rule(self):
        """Test registering a custom rule."""
        from code_tools.scripts.smart_ast.engine import SmartAstEngine, BUILTIN_RULES

        engine = SmartAstEngine()
        test_rule_name = f"test_rule_{id(engine)}"
        engine.register_rule(test_rule_name, "test($$$)", "Test rule message")
        assert test_rule_name in BUILTIN_RULES


class TestPatterns:
    """Test pattern utilities."""

    def test_language_patterns_python(self):
        """Test Python language patterns."""
        from code_tools.scripts.smart_ast.patterns import LANG_PATTERNS

        assert "class $NAME" in LANG_PATTERNS["python"]["classes"]
        assert "def $NAME($$$)" in LANG_PATTERNS["python"]["functions"]

    def test_language_patterns_rust(self):
        """Test Rust language patterns."""
        from code_tools.scripts.smart_ast.patterns import LANG_PATTERNS

        assert "struct $NAME" in LANG_PATTERNS["rust"]["structs"]
        assert "fn $NAME($$$)" in LANG_PATTERNS["rust"]["functions"]


class TestExtractAstPattern:
    """Test AST pattern extraction."""

    def test_extract_class_pattern(self):
        """Test extracting class patterns."""
        from code_tools.scripts.search.nodes.engines import extract_ast_pattern

        assert extract_ast_pattern("class User") == "class User"

    def test_extract_find_class_pattern(self):
        """Test extracting class patterns from find queries."""
        from code_tools.scripts.search.nodes.engines import extract_ast_pattern

        assert extract_ast_pattern("Find the User class") == "class User"

    def test_extract_function_pattern(self):
        """Test extracting function patterns."""
        from code_tools.scripts.search.nodes.engines import extract_ast_pattern

        assert extract_ast_pattern("def authenticate") == "def authenticate"

    def test_extract_fn_pattern(self):
        """Test extracting fn patterns (Rust)."""
        from code_tools.scripts.search.nodes.engines import extract_ast_pattern

        assert extract_ast_pattern("fn main") == "fn main"

    def test_extract_impl_pattern(self):
        """Test extracting impl patterns."""
        from code_tools.scripts.search.nodes.engines import extract_ast_pattern

        assert extract_ast_pattern("impl Foo") == "impl Foo"

    def test_extract_direct_pattern(self):
        """Test extracting direct patterns."""
        from code_tools.scripts.search.nodes.engines import extract_ast_pattern

        assert extract_ast_pattern("connect($$$)") == "connect($$$)"


class TestClassifier:
    """Test query classifier for intent recognition."""

    def test_classify_structural_class(self):
        """Test classifying class queries."""
        from code_tools.scripts.search.nodes.classifier import classify_query

        state = {"query": "class User"}
        result = classify_query(state)
        assert "ast" in result["strategies"]

    def test_classify_structural_function(self):
        """Test classifying function queries."""
        from code_tools.scripts.search.nodes.classifier import classify_query

        state = {"query": "def authenticate"}
        result = classify_query(state)
        assert "ast" in result["strategies"]

    def test_classify_semantic(self):
        """Test classifying semantic queries."""
        from code_tools.scripts.search.nodes.classifier import classify_query

        state = {"query": "how does authentication work?"}
        result = classify_query(state)
        assert "vector" in result["strategies"]

    def test_classify_grep_todo(self):
        """Test classifying TODO queries."""
        from code_tools.scripts.search.nodes.classifier import classify_query

        state = {"query": "TODO: fix"}
        result = classify_query(state)
        assert "grep" in result["strategies"]


class TestGraph:
    """Test graph creation."""

    def test_create_search_graph(self):
        """Test search graph creation."""
        from code_tools.scripts.search.graph import create_search_graph

        graph = create_search_graph()
        assert graph is not None

    def test_create_initial_state(self):
        """Test initial state creation."""
        from code_tools.scripts.search.graph import create_initial_state

        state = create_initial_state("test query", "test-thread")
        assert state["query"] == "test query"
        assert state["thread_id"] == "test-thread"


class TestState:
    """Test state types."""

    def test_search_result_type(self):
        """Test SearchResult type."""
        from code_tools.scripts.search.state import SearchResult

        result: SearchResult = {
            "engine": "ast",
            "file": "test.py",
            "line": 10,
            "content": "def test():",
            "score": 0.9,
        }
        assert result["engine"] == "ast"
        assert result["score"] == 0.9


class TestYAMLRules:
    """Test YAML rules loading."""

    def test_yaml_rules_exist(self):
        """Test that YAML rules files exist."""
        from pathlib import Path

        rules_dir = Path(__file__).parent.parent / "scripts" / "smart_ast" / "rules"
        if rules_dir.exists():
            yaml_files = list(rules_dir.glob("*.yaml"))
            assert len(yaml_files) > 0

    def test_rules_loaded_by_engine(self):
        """Test that YAML rules are loaded by engine."""
        from code_tools.scripts.smart_ast.engine import SmartAstEngine

        engine = SmartAstEngine()
        rules = engine.list_rules()
        assert len(rules) > 0


class TestCodeSearchIntegration:
    """Integration tests for code_search command."""

    def test_code_search_module_imports(self):
        """Test that all modules can be imported."""
        from code_tools.scripts.search.commands import code_search
        from code_tools.scripts.search.graph import get_search_graph

        assert callable(code_search)
        assert get_search_graph() is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
