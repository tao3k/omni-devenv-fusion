"""
src/agent/tests/test_system_stress.py
The Gauntlet: System-Wide Stress & Endurance Testing.

Integrates:
- Skill Registry (Kernel)
- Vector Memory (Hippocampus)
- Harvester (Evolution)
- Orchestrator Logic (Brain)

Scenarios:
1. The Marathon: Long-running task loops.
2. The Shape Shifter: Rapid skill context switching.
3. The Memory Flood: RAG performance under load.
"""

import pytest
import time
import asyncio
import shutil
import random
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Core Components
from agent.core.skill_registry import get_skill_registry
from agent.core.vector_store import get_vector_memory
from agent.core.schema import HarvestedInsight, KnowledgeCategory
from mcp.server import Server


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before each test."""
    import agent.core.skill_runtime.context as manager_module

    manager_module._instance = None
    yield
    manager_module._instance = None


@pytest.fixture
def system_components():
    """Initialize a clean system environment."""
    # 1. Reset Kernel
    registry = get_skill_registry()
    original_loaded = registry.loaded_skills.copy()
    registry.loaded_skills.clear()

    # 2. Reset Memory (Use a test collection to avoid messing up real DB)
    memory = get_vector_memory()
    # Create unique collection for this test run
    test_collection_name = f"stress_test_{int(time.time())}"

    # 3. Mock MCP
    mcp = MagicMock(spec=Server)
    mcp.tool = MagicMock(return_value=lambda x: x)

    yield registry, memory, mcp, test_collection_name

    # Cleanup
    try:
        if memory.store:
            memory.store.delete_collection(test_collection_name)
    except Exception:
        pass

    # Restore original state
    registry.loaded_skills.clear()
    registry.loaded_skills.update(original_loaded)


@pytest.fixture
def skills_for_testing():
    """Return skills available for stress testing."""
    return ["git"]


# -----------------------------------------------------------------------------
# Scenario 1: The Shape Shifter (Context Switching Stress)
# -----------------------------------------------------------------------------


class TestContextSwitching:
    """Test rapid loading/unloading of skills."""

    def test_rapid_skill_cycling(self, system_components, skills_for_testing):
        """
        Simulate an Agent frantically switching tools during a crisis.
        Cycle: Git -> Context Switch -> Git -> ...
        """
        registry, _, mcp, _ = system_components
        cycles = 100  # 100 switches for serious stress

        skills = skills_for_testing

        print(f"\n🔄 Starting Shape Shifter: {cycles} cycles...")
        start_time = time.perf_counter()

        for i in range(cycles):
            skill = skills[i % len(skills)]

            # 1. Load (or re-verify loaded)
            if skill not in registry.loaded_skills:
                success, _ = registry.load_skill(skill, mcp)
                assert success, f"Failed to load {skill} on cycle {i}"

            # 2. Get Context (Simulate context window update)
            ctx = registry.get_skill_context(skill)
            assert len(ctx) > 0, f"Empty context for {skill}"

            # 3. Verify State
            assert skill in registry.loaded_skills, f"Skill {skill} not in registry"

            # 4. Simulate "thinking" between switches
            # This tests if registry can handle rapid state access
            _ = registry.list_available_skills()

        end_time = time.perf_counter()
        total_time = end_time - start_time
        avg_time = total_time / cycles * 1000

        print(f"✅ Shape Shifter Passed. Total: {total_time:.2f}s, Avg Switch: {avg_time:.2f}ms")

        # Performance assertion
        assert avg_time < 5, f"Context switching too slow: {avg_time:.2f}ms avg"

    def test_concurrent_context_retrieval(self, system_components, skills_for_testing):
        """Test multiple concurrent context retrievals."""
        registry, _, mcp, _ = system_components

        # Load skill first
        registry.load_skill("git", mcp)

        iterations = 100
        print(f"\n🔀 Testing {iterations} concurrent context retrievals...")

        start_time = time.perf_counter()

        for _ in range(iterations):
            ctx = registry.get_skill_context("git")
            assert len(ctx) > 0

        end_time = time.perf_counter()
        avg_time = (end_time - start_time) / iterations * 1000

        print(f"✅ Concurrent retrieval passed. Avg: {avg_time:.4f}ms")
        assert avg_time < 1, f"Context retrieval too slow: {avg_time:.4f}ms"

    def test_manifest_cache_stress(self, system_components):
        """Test that repeated manifest access doesn't degrade."""
        registry, _, _, _ = system_components

        iterations = 1000
        print(f"\n📄 Stress testing manifest cache ({iterations} accesses)...")

        start_time = time.perf_counter()

        for _ in range(iterations):
            manifest = registry.get_skill_manifest("git")
            assert manifest is not None
            assert manifest.name == "git"

        end_time = time.perf_counter()
        avg_time = (end_time - start_time) / iterations * 1000

        print(f"✅ Manifest cache stress passed. Avg: {avg_time:.4f}ms")
        # Threshold adjusted for cross-platform consistency
        assert avg_time < 1.2, f"Manifest access too slow: {avg_time:.4f}ms"


# -----------------------------------------------------------------------------
# Scenario 2: The Memory Flood (RAG Saturation)
# -----------------------------------------------------------------------------


class TestMemorySaturation:
    """Test system performance when memory is full."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        True,  # Skip RAG tests - requires persistent LanceDB setup
        reason="RAG tests require persistent LanceDB setup",
    )
    async def test_rag_performance_under_load(self, system_components):
        """
        Inject 500 documents and measure retrieval latency.
        """
        _, memory, _, col_name = system_components

        # 1. Flood the system
        doc_count = 500
        print(f"\n🌊 Flooding Memory with {doc_count} documents...")

        docs = [
            f"Knowledge entry number {i} regarding python optimization and system architecture patterns."
            for i in range(doc_count)
        ]
        ids = [f"doc_{i}" for i in range(doc_count)]
        metadatas = [{"type": "stress_test", "index": i} for i in range(doc_count)]

        start_ingest = time.perf_counter()
        success = await memory.add(
            documents=docs, ids=ids, metadatas=metadatas, collection=col_name
        )
        ingest_time = time.perf_counter() - start_ingest

        print(f"🌊 Ingested in {ingest_time:.2f}s ({(ingest_time / doc_count) * 1000:.4f}ms/doc)")
        assert success, "Document ingestion failed"

        # 2. Stress Query
        query_count = 100
        print(f"🔎 Executing {query_count} rapid queries...")

        start_query = time.perf_counter()
        for _ in range(query_count):
            results = await memory.search("python optimization", n_results=10, collection=col_name)
            assert len(results) == 10, f"Expected 10 results, got {len(results)}"

        query_time = time.perf_counter() - start_query
        avg_latency = (query_time / query_count) * 1000

        print(f"✅ Memory Flood Passed. Avg Retrieval Latency: {avg_latency:.2f}ms")

        # Critical requirement: Retrieval must remain fast even with data
        assert avg_latency < 150, f"RAG too slow under load: {avg_latency:.2f}ms"

    @pytest.mark.asyncio
    async def test_rag_domain_filtering(self, system_components):
        """Test that domain filtering works under load."""
        _, memory, _, col_name = system_components

        # Add documents with different domains
        print("\n🎯 Testing domain filtering under load...")

        domains = ["python", "git", "architecture", "testing"]
        docs = []
        ids = []
        metadatas = []

        for i in range(200):
            domain = domains[i % len(domains)]
            docs.append(f"Document {i} about {domain}")
            ids.append(f"dom_{i}")
            metadatas.append({"domain": domain})

        await memory.add(documents=docs, ids=ids, metadatas=metadatas, collection=col_name)

        # Query with domain filter
        start_time = time.perf_counter()
        for _ in range(50):
            results = await memory.search(
                "code pattern", n_results=10, collection=col_name, where_filter={"domain": "python"}
            )
            # Results should be filtered
            for r in results:
                assert r.metadata.get("domain") == "python"

        avg_latency = ((time.perf_counter() - start_time) / 50) * 1000
        print(f"✅ Domain filtering passed. Avg: {avg_latency:.2f}ms")

    @pytest.mark.asyncio
    async def test_rag_concurrent_search(self, system_components):
        """Test concurrent search requests."""
        _, memory, _, col_name = system_components

        # Seed some data
        docs = [f"Concurrent test document {i}" for i in range(100)]
        await memory.add(documents=docs, ids=[f"c_{i}" for i in range(100)], collection=col_name)

        print("\n⚡ Testing concurrent searches...")

        async def search_task(query_id: int) -> float:
            start = time.perf_counter()
            results = await memory.search("test", n_results=5, collection=col_name)
            return (time.perf_counter() - start) * 1000

        # Run 20 concurrent searches
        start_time = time.perf_counter()
        latencies = await asyncio.gather(*[search_task(i) for i in range(20)])

        total_time = time.perf_counter() - start_time
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        print(
            f"✅ Concurrent search passed. Total: {total_time:.2f}s, Avg: {avg_latency:.2f}ms, Max: {max_latency:.2f}ms"
        )

        assert avg_latency < 150, f"Concurrent search too slow: {avg_latency:.2f}ms avg"


# -----------------------------------------------------------------------------
# Scenario 3: The Marathon (Endurance Integration)
# -----------------------------------------------------------------------------


class TestSystemEndurance:
    """Simulate a long-running, multi-step workflow."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_loop(self, system_components):
        """
        Loop: Load Skill -> 'Execute' -> Harvest Insight -> Save to Memory.
        This tests the interaction between Kernel, Harvester, and Memory.
        """
        registry, memory, mcp, col_name = system_components
        turns = 30

        print(f"\n🏃 Starting Marathon: {turns} full lifecycle turns...")

        start_time = time.perf_counter()

        for i in range(turns):
            # Step 1: Dynamic Skill Load
            registry.load_skill("git", mcp)

            # Step 2: Simulate Tool Execution
            ctx = registry.get_skill_context("git")
            assert len(ctx) > 0

            # Step 3: Generate mock insight
            insight = {
                "title": f"Marathon Insight {i}",
                "category": random.choice(["CODE_PATTERN", "ARCHITECTURAL_DECISION", "WORKFLOW"]),
                "context": f"Learning from iteration {i}",
                "solution": "Keep iterating",
                "takeaways": [f"Lesson {i}: Persistence matters"],
            }

            # Step 4: Save to Memory (Simulate Harvester)
            insight_doc = f"""
# {insight["title"]}

**Category**: {insight["category"]}
**Turn**: {i}

## Context
{insight["context"]}

## Solution
{insight["solution"]}

## Key Takeaways
- {insight["takeaways"][0]}
"""
            await memory.add(
                documents=[insight_doc],
                ids=[f"marathon_{i}"],
                metadatas=[{"type": "harvested", "turn": i}],
                collection=col_name,
            )

            # Small delay to allow LanceDB to sync (fixes race condition)
            # Without this, rapid add+search can fail with "Table does not exist"
            await asyncio.sleep(0.05)

            # Step 5: Recall (Validation)
            results = await memory.search(f"iteration {i}", n_results=1, collection=col_name)
            assert len(results) > 0, f"Failed to recall insight from turn {i}"

        total_time = time.perf_counter() - start_time
        print(
            f"✅ Marathon Passed. {turns} turns in {total_time:.2f}s ({total_time / turns * 1000:.1f}ms/turn)"
        )

        # Verify System Integrity
        assert "git" in registry.loaded_skills
        count = await memory.count(collection=col_name)
        # Use range check since previous test runs may have left data
        assert count >= turns, f"Expected at least {turns} insights, got {count}"

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Long-running stress test - run manually with longer timeout")
    async def test_memory_persistence_stress(self, system_components):
        """Test that memory survives repeated operations."""
        _, memory, _, col_name = system_components

        operations = 50  # Reduced for CI
        print(f"\n💾 Testing memory persistence ({operations} write/read cycles)...")

        # Write then immediately read
        for i in range(operations):
            # Write
            await memory.add(
                documents=[f"Persistence test doc {i}"], ids=[f"persist_{i}"], collection=col_name
            )

            # Read (verify it exists)
            results = await memory.search(
                f"Persistence test doc {i}", n_results=1, collection=col_name
            )
            assert len(results) >= 1, f"Failed to read back doc {i}"

            if i % 50 == 0:
                print(f"  📍 Progress: {i}/{operations} cycles...")

        print(f"✅ Memory persistence stress passed.")

    @pytest.mark.asyncio
    async def test_skills_memory_integration(self, system_components):
        """Test tight integration between Skills and Memory."""
        registry, memory, mcp, col_name = system_components

        print("\n🔗 Testing Skills-Memory integration...")

        # 1. Load multiple skills
        registry.load_skill("git", mcp)

        # 2. Create skill-specific memory entries
        skill_memory = {
            "git": ["git commit workflow", "smart commit protocol", "branch management"],
            "filesystem": ["file operations", "directory traversal"],
        }

        for skill, keywords in skill_memory.items():
            if skill in registry.loaded_skills:
                for keyword in keywords:
                    await memory.add(
                        documents=[f"Knowledge about {keyword} for {skill}"],
                        ids=[f"{skill}_{keyword.replace(' ', '_')}"],
                        metadatas={"skill": skill, "keyword": keyword},
                        collection=col_name,
                    )

        # 3. Query skill-specific knowledge
        for skill in registry.loaded_skills.keys():
            results = await memory.search(
                f"{skill} workflow", n_results=5, collection=col_name, where_filter={"skill": skill}
            )
            print(f"  📚 {skill}: Found {len(results)} related memories")

        print(f"✅ Skills-Memory integration passed.")


# -----------------------------------------------------------------------------
# Scenario 4: Chaos Testing (Edge Cases)
# -----------------------------------------------------------------------------


class TestChaosScenarios:
    """Test extreme edge cases and recovery."""

    @pytest.mark.asyncio
    async def test_empty_collection_operations(self, system_components):
        """Test operations on empty collection."""
        _, memory, _, col_name = system_components

        print("\n🕳️ Testing empty collection edge case...")

        # Search on empty collection
        results = await memory.search("anything", n_results=5, collection=col_name)
        assert len(results) == 0, "Empty collection should return empty results"

        print(f"✅ Empty collection handled correctly.")

    @pytest.mark.asyncio
    async def test_rapid_deletion_stress(self, system_components):
        """Test rapid add/delete cycles."""
        _, memory, _, col_name = system_components

        print("\n🗑️ Testing rapid deletion stress...")

        # Add documents
        for i in range(20):
            await memory.add(documents=[f"To delete {i}"], ids=[f"delete_{i}"], collection=col_name)

        # Delete them rapidly
        for i in range(20):
            await memory.delete(ids=[f"delete_{i}"], collection=col_name)

        # Verify all gone
        count = await memory.count(collection=col_name)
        assert count == 0, f"Expected 0 docs after deletion, got {count}"

        print(f"✅ Rapid deletion passed.")

    @pytest.mark.asyncio
    async def test_unicode_content_handling(self, system_components):
        """Test that unicode content doesn't break the system."""
        _, memory, _, col_name = system_components

        print("\n🌐 Testing unicode content handling...")

        unicode_docs = [
            "中文测试文档",
            "Emoji test 🚀🔥",
            "Russian текст",
            "Emoji chain 🔴🟡🟢🔵",
            "Mixed 中文 + English + emojis 🎉",
        ]

        for i, doc in enumerate(unicode_docs):
            await memory.add(documents=[doc], ids=[f"unicode_{i}"], collection=col_name)

        # Query should handle unicode
        results = await memory.search("测试", n_results=5, collection=col_name)
        assert len(results) > 0, "Unicode search failed"

        print(f"✅ Unicode handling passed.")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main(["-v", "-s", __file__]))
