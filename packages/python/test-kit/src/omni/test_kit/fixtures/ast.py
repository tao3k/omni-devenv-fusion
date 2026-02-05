"""
AST Test Helpers - Simplify AST search and analysis testing

Provides helper functions for testing:
- Query classification (structural/semantic/grep)
- Pattern extraction from natural language
- Sample code for testing

Usage:
    from omni.test_kit.fixtures.ast import classify_query_helper, extract_ast_pattern_helper

    # Test classifier
    result = classify_query_helper("class User")
    assert "ast" in result["strategies"]

    # Test pattern extraction
    pattern = extract_ast_pattern_helper("def authenticate")
    assert pattern == "def authenticate"
"""

from typing import List, Tuple


# Semantic test cases for classifier validation
SEMANTIC_TEST_CASES: List[Tuple[str, str]] = [
    # Structural queries -> AST
    ("class User", "ast"),
    ("def authenticate", "ast"),
    ("fn main", "ast"),
    ("struct User", "ast"),
    ("impl Foo", "ast"),
    # Semantic queries -> Vector
    ("how does authentication work", "vector"),
    ("what is the architecture", "vector"),
    ("why is this failing", "vector"),
    # Exact match queries -> Grep
    ("TODO: fix", "grep"),
    ("FIXME: memory leak", "grep"),
    ('"error message"', "grep"),
]


def classify_query_helper(query: str) -> dict:
    """Helper for classifier testing.

    Creates minimal state and runs classify_query.
    Returns the classification result dict.
    """
    from datetime import datetime
    from code_tools.scripts.search.nodes.classifier import classify_query

    state = {
        "query": query,
        "strategies": [],
        "raw_results": [],
        "iteration": 0,
        "needs_clarification": False,
        "clarification_prompt": "",
        "final_output": "",
        "thread_id": "test",
        "timestamp": datetime.now().isoformat(),
    }
    return classify_query(state)


def extract_ast_pattern_helper(query: str) -> str:
    """Helper for AST pattern extraction.

    Returns the extracted pattern or None if query is not structural.
    """
    from code_tools.scripts.search.nodes.engines import extract_ast_pattern

    return extract_ast_pattern(query)


# Sample code fixtures (as strings for easy use)
SAMPLE_PYTHON_CODE = '''
class User:
    """User class for authentication."""
    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

    async def authenticate(self, password: str) -> bool:
        return True

def login(username: str, password: str) -> User:
    return User(username, f"{username}@example.com")
'''

SAMPLE_RUST_CODE = """
struct User {
    name: String,
    email: String,
}

impl User {
    fn new(name: String, email: String) -> Self {
        User { name, email }
    }
}

fn main() {
    println!("Hello, World!");
}
"""
