"""
Librarian (Vector Memory / RAG) Test Suite

Tests for:
- consult_knowledge_base: Semantic search
- ingest_knowledge: Add documents to vector store
- bootstrap_knowledge: Initialize knowledge base
- list_knowledge_domains: List collections
- search_project_rules: Search project rules

Run: uv run python src/common/mcp_server/tests/test_librarian.py
"""
import asyncio
import json
import os

from agent.core.vector_store import get_vector_memory


def cleanup_test_data():
    """Clean up any test data from previous runs."""
    vm = get_vector_memory()
    if vm.client:
        try:
            collections = vm.client.list_collections()
            for coll in collections:
                if coll.name.startswith("test_"):
                    vm.client.delete_collection(coll.name)
        except Exception:
            pass


def test_vector_store_import():
    """Test that vector_store module imports correctly."""
    print("\n=== Test: Vector Store Import ===")
    try:
        from agent.core.vector_store import (
            VectorMemory,
            get_vector_memory,
            search_knowledge,
            ingest_knowledge,
            SearchResult,
        )
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_librarian_import():
    """Test that librarian module imports correctly."""
    print("\n=== Test: Librarian Import ===")
    try:
        from agent.capabilities.librarian import register_librarian_tools
        print("✅ Librarian imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_librarian_tools_registration():
    """Test that librarian tools are properly registered."""
    print("\n=== Test: Librarian Tools Registration ===")
    try:
        from mcp.server.fastmcp import FastMCP
        from agent.capabilities.librarian import register_librarian_tools

        mcp = FastMCP("test")
        register_librarian_tools(mcp)

        expected_tools = [
            "consult_knowledge_base",
            "ingest_knowledge",
            "bootstrap_knowledge",
            "list_knowledge_domains",
            "search_project_rules",
        ]

        registered = [t.name for t in mcp._tool_manager.list_tools()]

        missing = [t for t in expected_tools if t not in registered]
        if missing:
            print(f"❌ Missing tools: {missing}")
            return False

        print(f"✅ All {len(expected_tools)} tools registered: {registered}")
        return True
    except Exception as e:
        print(f"❌ Registration failed: {e}")
        return False


async def test_ingest_and_search():
    """Test ingesting and searching knowledge."""
    print("\n=== Test: Ingest and Search ===")

    vm = get_vector_memory()

    # Clean up test collection
    try:
        if vm.client:
            vm.client.delete_collection("test_librarian")
    except Exception:
        pass

    # Test data
    test_docs = [
        "Git commits must use smart_commit tool for authorization.",
        "Direct git commit is prohibited without authorization token.",
        "Conventional commits format: type(scope): description"
    ]
    test_ids = ["test-git-001", "test-git-002", "test-git-003"]

    # Ingest into a specific collection
    collection_name = "test_librarian"
    success = await vm.add(
        documents=test_docs,
        ids=test_ids,
        collection=collection_name,
        metadatas=[{"domain": "git", "priority": "high"}] * 3
    )

    if not success:
        print("❌ Failed to ingest test data")
        return False

    print("✅ Test data ingested")

    # Search in the same collection
    results = await vm.search("how to commit changes", n_results=3, collection=collection_name)

    if len(results) == 0:
        # Debug: search without collection filter
        all_results = await vm.search("git", n_results=5)
        print(f"❌ Search returned no results (debug: found {len(all_results)} in default collection)")
        return False

    print(f"✅ Search returned {len(results)} results")
    for r in results:
        print(f"   - [{r.id}] relevance: {1.0 - r.distance:.2f}")

    # Cleanup
    await vm.delete(ids=test_ids, collection=collection_name)
    print("✅ Test data cleaned up")

    return True


async def test_search_result_format():
    """Test SearchResult dataclass format."""
    print("\n=== Test: Search Result Format ===")

    vm = get_vector_memory()

    # Ingest test data
    await vm.add(
        documents=["Test document for format verification."],
        ids=["test-format-001"],
        metadatas=[{"domain": "test"}]
    )

    # Search
    results = await vm.search("test document format", n_results=1)

    if not results:
        print("❌ No results returned")
        return False

    r = results[0]

    # Verify all attributes exist
    required_attrs = ["content", "metadata", "distance", "id"]
    missing = [a for a in required_attrs if not hasattr(r, a)]
    if missing:
        print(f"❌ Missing attributes: {missing}")
        return False

    print(f"✅ SearchResult format correct:")
    print(f"   - id: {r.id}")
    print(f"   - content length: {len(r.content)}")
    print(f"   - metadata: {r.metadata}")
    print(f"   - distance: {r.distance}")

    # Cleanup
    await vm.delete(ids=["test-format-001"])

    return True


async def test_domain_filtering():
    """Test domain-based filtering."""
    print("\n=== Test: Domain Filtering ===")

    vm = get_vector_memory()

    # Ingest documents with different domains
    await vm.add(
        documents=["Git workflow rule."],
        ids=["domain-test-001"],
        collection="test_domain",
        metadatas=[{"domain": "git"}]
    )
    await vm.add(
        documents=["Architecture decision."],
        ids=["domain-test-002"],
        collection="test_domain",
        metadatas=[{"domain": "architecture"}]
    )
    await vm.add(
        documents=["Coding standard for Python."],
        ids=["domain-test-003"],
        collection="test_domain",
        metadatas=[{"domain": "standards"}]
    )

    # Search with domain filter
    git_results = await vm.search("rule", n_results=10, collection="test_domain", where_filter={"domain": "git"})

    if len(git_results) == 1 and "domain-test-001" in git_results[0].id:
        print("✅ Domain filter works - only git results returned")
    else:
        print(f"❌ Domain filter failed - got {len(git_results)} results")
        return False

    # Search without filter (should get all)
    all_results = await vm.search("rule OR architecture OR python", n_results=10, collection="test_domain")
    if len(all_results) >= 3:
        print("✅ Unfiltered search returns all domains")
    else:
        print(f"❌ Unfiltered search failed - expected 3+ results, got {len(all_results)}")
        return False

    # Cleanup
    await vm.delete(ids=["domain-test-001", "domain-test-002", "domain-test-003"], collection="test_domain")

    return True


async def test_multiple_collections():
    """Test multiple collections support."""
    print("\n=== Test: Multiple Collections ===")

    vm = get_vector_memory()

    # Ingest into different collections
    await vm.add(
        documents=["Git workflow rule."],
        ids=["col-test-001"],
        collection="git_rules"
    )
    await vm.add(
        documents=["Architecture decision."],
        ids=["col-test-002"],
        collection="architecture"
    )

    # Search specific collection
    git_results = await vm.search("workflow", n_results=5, collection="git_rules")
    arch_results = await vm.search("architecture", n_results=5, collection="architecture")

    # Verify results are from correct collections
    if git_results and "col-test-001" in git_results[0].id:
        print("✅ Git collection search works")
    else:
        print("❌ Git collection search failed")
        return False

    if arch_results and "col-test-002" in arch_results[0].id:
        print("✅ Architecture collection search works")
    else:
        print("❌ Architecture collection search failed")
        return False

    # Cleanup
    await vm.delete(ids=["col-test-001"], collection="git_rules")
    await vm.delete(ids=["col-test-002"], collection="architecture")

    return True


async def run_async_tests():
    """Run all async tests."""
    tests = [
        ("Ingest and Search", test_ingest_and_search),
        ("Search Result Format", test_search_result_format),
        ("Domain Filtering", test_domain_filtering),
        ("Multiple Collections", test_multiple_collections),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = await test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    return results


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 Librarian (Vector Memory / RAG) Test Suite")
    print("=" * 60)

    # Sync tests
    sync_tests = [
        ("Vector Store Import", test_vector_store_import),
        ("Librarian Import", test_librarian_import),
        ("Tools Registration", test_librarian_tools_registration),
    ]

    results = []

    for name, test_fn in sync_tests:
        try:
            result = test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} failed with exception: {e}")
            results.append((name, False))

    # Async tests
    print("\n--- Async Tests ---")
    async_results = asyncio.run(run_async_tests())
    results.extend(async_results)

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
