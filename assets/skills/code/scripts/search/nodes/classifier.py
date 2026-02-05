"""
Query Classifier - Intent Recognition for Search Routing

Uses lightweight heuristics (no LLM call) to determine:
- AST search: Code structure queries (class def, function signatures)
- Vector search: Semantic/conceptual queries (natural language)
- Grep search: Exact text matches (TODOs, error codes, quoted strings)
"""

import re
from typing import List

from ..state import SearchGraphState


# Heuristic patterns for strategy detection
STRUCTURAL_PATTERNS = [
    r"\bclass\s+\w+",  # class Foo (exact)
    r"\bclass\s+\w+(?:\s+\w+)*\s+class\b",  # class X class Y (alternative)
    r"\bdef\s+\w+",  # def foo
    r"\bfn\s+\w+",  # fn foo (Rust)
    r"\bimpl\s+\w+",  # impl Foo
    r"\bstruct\s+\w+",  # struct Foo
    r"\binterface\s+\w+",  # interface Foo
    r"\benum\s+\w+",  # enum Foo
    r"::",  # :: (Rust/JS namespaces)
    r"->",  # Return type annotation
    r"\$\w+",  # Variable patterns
]

# Additional patterns for loose matching (separated by words like "the", "of")
LOOSE_STRUCTURAL_PATTERNS = [
    (r"\bclass\s+\w+", True),  # class Foo - exact
    (r"\bclass\s+(\w+\s+){1,3}class\b", True),  # class X class Y
    (r"\b(?:define|definition|of)\s+\w+", False),  # definition of X - might be structural
    (
        r"\b(?:find|search|locate)\s+(?:the\s+)?(?:definition\s+of\s+)?\w+\s+\w+",
        False,
    ),  # Find the definition of X
]

EXACT_MATCH_PATTERNS = [
    r'^".*"$',  # Quoted strings
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\bXXX\b",
    r"Error\s*\d{3,}",  # Error codes
    r"Exception:",  # Python exceptions
]

SEMANTIC_INDICATORS = [
    "how",
    "what",
    "why",  # Questions
    "implement",
    "handle",  # Implementation queries
    "work",
    "logic",  # Conceptual queries
    "pattern",
    "architecture",
]


def classify_query(state: SearchGraphState) -> dict:
    """Classify the query and determine search strategies.

    This runs BEFORE entering the main graph state machine,
    determining which branches to execute in parallel.
    """
    query = state.get("query", "").strip()
    query_lower = query.lower()

    strategies = []
    reasoning_parts = []

    # Check for structural patterns (AST)
    has_structural = any(re.search(p, query) for p in STRUCTURAL_PATTERNS)

    # Also check loose structural patterns
    # e.g., "Find the definition of the Librarian class" -> class Librarian
    if not has_structural:
        for pattern, _ in LOOSE_STRUCTURAL_PATTERNS:
            if re.search(pattern, query_lower):
                has_structural = True
                break

    if has_structural:
        strategies.append("ast")
        reasoning_parts.append("AST: detected structural patterns")

    # Check for exact match indicators (Grep)
    has_exact = any(re.search(p, query) for p in EXACT_MATCH_PATTERNS)
    # Also check for file extensions (e.g., "*.py")
    has_file_pattern = re.search(r"\*\.\w+", query)
    if has_exact or has_file_pattern:
        strategies.append("grep")
        reasoning_parts.append("Grep: detected exact-match patterns")

    # Default to semantic for questions and conceptual queries
    is_question = query.endswith("?") or any(q in query_lower for q in SEMANTIC_INDICATORS)
    if not strategies or is_question:
        if "vector" not in strategies:
            strategies.append("vector")
            if is_question:
                reasoning_parts.append("Vector: detected question format")
            elif not strategies:
                reasoning_parts.append("Vector: default to semantic search")

    # Determine confidence
    if has_structural or has_exact:
        confidence = 0.9
    elif is_question:
        confidence = 0.7
    else:
        confidence = 0.5

    # If no strategies determined, include all
    if not strategies:
        strategies = ["ast", "vector", "grep"]
        reasoning_parts.append("Fallback: all strategies")

    return {
        "strategies": strategies,
        "confidence": confidence,
        "reasoning": "; ".join(reasoning_parts),
    }


def classify_intent(state: SearchGraphState) -> dict:
    """Main classifier node for the graph.

    Returns state updates for the graph flow.
    """
    result = classify_query(state)

    # Create clarification prompt if confidence is low
    needs_clarification = result["confidence"] < 0.5
    clarification_prompt = ""
    if needs_clarification:
        clarification_prompt = (
            f"Your query '{state['query']}' is ambiguous. "
            f"Detected patterns: {result['reasoning']}. "
            f"Consider using more specific terms like 'class Foo' or 'def bar'."
        )

    return {
        "strategies": result["strategies"],
        "confidence": result["confidence"],
        "clarification_prompt": clarification_prompt,
        "needs_clarification": needs_clarification,
    }
