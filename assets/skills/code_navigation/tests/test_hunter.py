#!/usr/bin/env python3
"""
scripts/test_hunter.py
Phase 51: The Hunter - Structural Code Search Verification

Demonstrates the precision of AST-based code search compared to naive grep.

The Hunter Principle: "Hunt with precision, not with a net."
- Naive grep finds strings (including comments and strings)
- AST search finds CODE PATTERNS (semantic matching)

Usage:
    python scripts/test_hunter.py [--pattern <pattern>] [--path <path>]

Example:
    python scripts/test_hunter.py --pattern "class $NAME" --path packages/python/agent/src/agent/
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "packages/python/agent/src"))

from agent.core.context_compressor import count_tokens

# Try to import Rust bindings
try:
    import omni_core_rs

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    print("[WARNING] omni_core_rs not available. Running in fallback mode.")


def naive_grep_search(content: str, pattern: str) -> list[tuple[int, str]]:
    """Traditional text-based search (what grep does)."""
    lines = content.split("\n")
    results = []
    for i, line in enumerate(lines, 1):
        if pattern in line:
            results.append((i, line.strip()))
    return results


def test_search_precision():
    """
    Test that AST search is more precise than naive grep.

    Example: Searching for "class Agent" should find class definitions,
    not the word "class" in comments or strings.
    """
    # Create a test file with various occurrences of "connect"
    test_code = '''
# This is a comment about connect function
# Don't connect to unauthorized servers

def connect(host: str, port: int) -> bool:
    """Connect to a server."""
    if host == "unauthorized":
        return False  # We don't connect here
    return True

# Connecting is important
# TODO: Connect to database later

class DatabaseConnector:
    def connect(self, db_url: str):
        """Method to connect to database."""
        pass

# The word connect appears many times above
'''

    print("=" * 60)
    print("Phase 51: The Hunter - Search Precision Test")
    print("=" * 60)
    print()

    # Naive grep results
    grep_results = naive_grep_search(test_code, "connect")
    print(f"Naive grep 'connect' found {len(grep_results)} matches:")
    for line_num, line in grep_results:
        print(f"  L{line_num}: {line[:60]}...")

    print()

    # AST-based search (when available)
    if RUST_AVAILABLE:
        try:
            # Write test file
            test_file = PROJECT_ROOT / ".test_hunter.py"
            test_file.write_text(test_code)

            ast_results = omni_core_rs.search_code(str(test_file), "connect($ARGS)")
            print(f"AST search 'connect($ARGS)' results:")
            print(ast_results)

            # Count only actual function calls (should be 2: the connect function def and the method)
            actual_calls = ast_results.count("def connect") + ast_results.count("def connect")
            print(f"\nPrecision: AST search found {actual_calls} actual function patterns")
            print(f"Naive grep found {len(grep_results)} text occurrences")

            # Cleanup
            test_file.unlink()

        except Exception as e:
            print(f"Error with AST search: {e}")
    else:
        print("[INFO] AST search not available. Install Rust bindings to test.")


def test_pattern_examples():
    """Test various AST patterns."""
    print()
    print("=" * 60)
    print("Phase 51: Pattern Examples")
    print("=" * 60)
    print()

    if not RUST_AVAILABLE:
        print("[INFO] AST search not available. Run 'just build-rust' to enable.")
        return

    patterns = [
        ("def $NAME", "Find all function definitions"),
        ("class $NAME", "Find all class definitions"),
        ("async def $NAME", "Find all async function definitions"),
    ]

    target_file = "packages/python/agent/src/agent/core/agents/base.py"

    if not Path(target_file).exists():
        print(f"[WARNING] Target file not found: {target_file}")
        return

    for pattern, description in patterns:
        print(f"\n{description}:")
        print(f"  Pattern: {pattern}")
        try:
            result = omni_core_rs.search_code(target_file, pattern)
            # Count matches
            lines = [l for l in result.split("\n") if l.strip() and not l.startswith("//")]
            print(f"  Found {len(lines)} matches")
        except Exception as e:
            print(f"  Error: {e}")


def format_comparison(grep_count: int, ast_count: int, pattern: str) -> str:
    """Format a comparison between grep and AST search."""
    return f"""
Search Comparison for pattern '{pattern}':
  Naive grep: {grep_count} text occurrences
  AST search: {ast_count} semantic matches
  Precision gain: {grep_count / max(1, ast_count):.1f}x fewer false positives
"""


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Test Phase 51: The Hunter - Structural Code Search"
    )
    parser.add_argument(
        "--pattern",
        default="def $NAME",
        help="AST pattern to search for",
    )
    parser.add_argument(
        "--path",
        default="packages/python/agent/src/agent/",
        help="Path to search in",
    )
    parser.add_argument(
        "--precision",
        action="store_true",
        help="Run precision comparison test",
    )

    args = parser.parse_args()

    if args.precision:
        test_search_precision()
    else:
        test_pattern_examples()

    print()
    print("=" * 60)
    print("Phase 51: The Hunter Summary")
    print("=" * 60)
    print()
    print("The Hunter Principle: 'Hunt with precision, not with a net.'")
    print()
    print("Benefits over naive grep:")
    print("  1. Semantic matching - finds code, not text")
    print("  2. Pattern capture - extract matched parts with $VAR")
    print("  3. Language awareness - understands code structure")
    print("  4. Reduced noise - ignores comments and strings")
    print()


if __name__ == "__main__":
    main()
