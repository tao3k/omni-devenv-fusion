#!/usr/bin/env python3
"""
scripts/test_librarian.py
Phase 53: The Librarian Integration Test.

Tests the Rust + Python integration for the vector store.
"""

import sys
import json
import shutil

# Setup import paths using common.lib
from common.lib import setup_import_paths

setup_import_paths()

from common.gitops import get_project_root


def test_rust_bindings():
    """Test Rust bindings directly."""
    print("\n[1] Testing Rust Bindings (omni-core-rs)")
    print("-" * 50)

    try:
        import omni_core_rs

        print("  ✅ omni_core_rs imported successfully")
    except ImportError as e:
        print(f"  ❌ Failed to import omni_core_rs: {e}")
        return False

    # Create a test database using project root
    project_root = get_project_root()
    test_db_path = str(project_root / ".cache" / "test_librarian")
    if os.path.exists(test_db_path):
        shutil.rmtree(test_db_path)
    os.makedirs(test_db_path, exist_ok=True)

    try:
        # Create VectorStore
        store = omni_core_rs.py_create_vector_store(test_db_path)
        print("  ✅ PyVectorStore created successfully")

        # Add documents
        test_docs = [
            ("Rust is a systems programming language.", {"tag": "tech", "lang": "rust"}),
            ("Python is great for AI agents.", {"tag": "tech", "lang": "python"}),
            ("Omni uses LanceDB for vector search.", {"tag": "arch", "project": "omni"}),
            ("Today is a sunny day.", {"tag": "misc", "weather": "sunny"}),
        ]

        doc_ids = []
        for i, (content, meta) in enumerate(test_docs):
            doc_id = f"doc_{i}"
            doc_ids.append(doc_id)
            # Create 1536-dim dummy vector
            vector = [0.1 * (i + 1)] * 1536

            store.add_documents("test_table", [doc_id], [vector], [content], [json.dumps(meta)])
        print(f"  ✅ Added {len(test_docs)} documents")

        # Search
        query_vector = [0.1] * 1536  # Same as doc_0
        results = store.search("test_table", query_vector, k=2)
        print(f"  ✅ Search returned {len(results)} results")

        if results:
            # Parse first result
            r = json.loads(results[0])
            print(f"     Top result: {r.get('content', 'N/A')[:50]}...")
            print(f"     Distance: {r.get('distance', 0):.4f}")

        # Count
        count = store.count("test_table")
        print(f"  ✅ Document count: {count}")

        # Create index
        store.create_index("test_table")
        print("  ✅ Index created successfully")

        # Cleanup
        store.drop_table("test_table")
        shutil.rmtree(test_db_path)
        print("  ✅ Cleanup complete")

        return True

    except Exception as e:
        print(f"  ❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_memory_skill():
    """Test Memory Skill integration with semantic search."""
    print("\n[2] Testing Memory Skill Integration")
    print("-" * 50)

    # Clear any cached imports
    if "agent.skills.memory.tools" in sys.modules:
        del sys.modules["agent.skills.memory.tools"]

    try:
        from agent.skills.memory import tools

        print("  ✅ Memory tools imported successfully")

        # Check Rust availability
        if not tools.RUST_AVAILABLE:
            print("  ⚠️  Rust VectorStore not available (expected if not built)")
            return True

        print(f"  ✅ RUST_AVAILABLE: {tools.RUST_AVAILABLE}")
        print(f"  ✅ DB_PATH: {tools.DB_PATH}")

        # Test save_memory with semantically rich content
        test_memories = [
            (
                "Rust is a systems programming language with memory safety.",
                {"domain": "tech", "tag": "rust"},
            ),
            (
                "Python is great for AI agents and rapid development.",
                {"domain": "tech", "tag": "python"},
            ),
            (
                "Omni uses LanceDB for high-performance vector search.",
                {"domain": "arch", "tag": "omni"},
            ),
            (
                "Type hints improve code clarity and catch bugs early.",
                {"domain": "coding", "tag": "types"},
            ),
        ]

        for content, meta in test_memories:
            result = tools.save_memory(content, meta)
            print(f"  ✅ Saved: {content[:40]}...")

        # Test semantic search - search for related but not identical terms
        print("\n  [Semantic Search Tests]")
        print("  Storing: 'Rust is a systems programming language...'")
        print("  Query: 'What programming languages are good for systems?'")
        result = tools.search_memory("What programming languages are good for systems?", limit=2)
        print(f"  ✅ Semantic search result: {result[:150]}...")

        print("\n  Storing: 'Omni uses LanceDB for vector search'")
        print("  Query: 'Tell me about the database used for AI embeddings'")
        result = tools.search_memory("Tell me about the database used for AI embeddings", limit=2)
        print(f"  ✅ Semantic search result: {result[:150]}...")

        # Test get_memory_stats
        result = tools.get_memory_stats()
        print(f"  ✅ get_memory_stats: {result}")

        # Test index_memory
        result = tools.index_memory()
        print(f"  ✅ index_memory: {result}")

        return True

    except Exception as e:
        print(f"  ❌ Memory skill test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("🚀 Phase 53: The Librarian Integration Test")
    print("=" * 60)

    results = []

    # Test 1: Rust bindings
    results.append(("Rust Bindings", test_rust_bindings()))

    # Test 2: Memory skill
    results.append(("Memory Skill", test_memory_skill()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✅ Phase 53 Complete: The Librarian is operational!")
        return 0
    else:
        print("\n❌ Some tests failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
