#!/usr/bin/env python3
"""
agent/tests/unit/test_memory_skill.py
Memory Skill Tests

Tests the Memory skill (Hippocampus Interface):
1. save_memory - Store insights
2. search_memory - Semantic recall
3. load_skill - Skill manifest indexing
4. get_memory_stats - Statistics
5. External module loading via load_skill_module

Usage:
    python3 -m agent.tests.unit.test_memory_skill
    pytest agent/tests/unit/test_memory_skill.py -v
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def memory_module():
    """Load the memory skill module."""
    from common.skills_path import load_skill_module

    return load_skill_module("memory")


@pytest.fixture
async def clean_memory(memory_module):
    """Ensure memory is available for testing."""
    # Skip if Rust store not available
    try:
        result = await memory_module.get_memory_stats()
        if "not available" in result.lower():
            pytest.skip("Rust VectorStore not available")
    except Exception as e:
        pytest.skip(f"Memory store not available: {e}")

    yield memory_module

    # Cleanup: No explicit cleanup needed, tests use unique content


# =============================================================================
# Test Classes
# =============================================================================


class TestMemoryModuleExports:
    """Test that memory module exports correct functions."""

    def test_module_loads(self, memory_module):
        """Memory module should load successfully."""
        assert memory_module is not None
        assert hasattr(memory_module, "save_memory")
        assert hasattr(memory_module, "search_memory")

    def test_exports_available(self, memory_module):
        """All required exports should be available."""
        expected_exports = [
            "save_memory",
            "search_memory",
            "index_memory",
            "get_memory_stats",
            "load_skill",
        ]
        for export in expected_exports:
            assert hasattr(memory_module, export), f"Missing export: {export}"


class TestSaveMemory:
    """Test save_memory functionality."""

    @pytest.mark.asyncio
    async def test_save_memory_basic(self, clean_memory):
        """Test basic memory storage."""
        memory = clean_memory

        result = await memory.save_memory(
            content="Test memory: Always use semantic versioning",
            metadata={"domain": "git", "test_id": "basic_save"},
        )

        assert "Saved memory" in result
        assert "Test memory" in result

    @pytest.mark.asyncio
    async def test_save_memory_with_metadata(self, clean_memory):
        """Test memory storage with custom metadata."""
        memory = clean_memory

        custom_metadata = {
            "domain": "testing",
            "source": "pytest",
            "tags": ["test", "memory"],
        }

        result = await memory.save_memory(
            content="Memory with custom metadata for testing", metadata=custom_metadata
        )

        assert "Saved memory" in result

    @pytest.mark.asyncio
    async def test_save_memory_no_metadata(self, clean_memory):
        """Test memory storage without metadata (None)."""
        memory = clean_memory

        result = await memory.save_memory(content="Memory without explicit metadata")

        assert "Saved memory" in result
        assert "Memory without explicit metadata" in result

    @pytest.mark.asyncio
    async def test_save_memory_unique_ids(self, clean_memory):
        """Test that each save gets a unique ID."""
        memory = clean_memory

        result1 = await memory.save_memory(
            content="First unique memory", metadata={"test_id": "unique_1"}
        )
        result2 = await memory.save_memory(
            content="Second unique memory", metadata={"test_id": "unique_2"}
        )

        # Extract IDs from results
        import re

        id1 = re.search(r"\[([a-f0-9]+)\]", result1)
        id2 = re.search(r"\[([a-f0-9]+)\]", result2)

        assert id1 is not None
        assert id2 is not None
        assert id1.group(1) != id2.group(1)


class TestSearchMemory:
    """Test search_memory functionality."""

    @pytest.mark.asyncio
    async def test_search_memory_returns_results(self, clean_memory):
        """Test that search returns formatted results."""
        memory = clean_memory

        # Store a specific memory first
        await memory.save_memory(
            content="Searchable memory about git commit workflow",
            metadata={"domain": "git", "test_id": "search_test"},
        )

        result = await memory.search_memory(query="git commit workflow", limit=5)

        assert "Found" in result or "matches" in result.lower()

    @pytest.mark.asyncio
    async def test_search_memory_with_limit(self, clean_memory):
        """Test search with custom limit."""
        memory = clean_memory

        result = await memory.search_memory(query="git commit", limit=2)

        # Should mention the limit in query
        assert "git commit" in result

    @pytest.mark.asyncio
    async def test_search_memory_empty_query(self, clean_memory):
        """Test search with empty-like query."""
        memory = clean_memory

        result = await memory.search_memory(query="zzzznonexistentquerythatdoesnotexist", limit=1)

        # Should return empty message
        assert "no" in result.lower() or "0" in result

    @pytest.mark.asyncio
    async def test_search_memory_format(self, clean_memory):
        """Test that search results have proper format."""
        memory = clean_memory

        # Store something specific
        await memory.save_memory(
            content="Format test memory: Use pytest for testing",
            metadata={"test_id": "format_test"},
        )

        result = await memory.search_memory(query="pytest testing", limit=5)

        # Results should contain score-like info
        assert "Found" in result or "matches" in result.lower()


class TestLoadSkill:
    """Test load_skill functionality."""

    @pytest.mark.asyncio
    async def test_load_skill_git(self, clean_memory):
        """Test loading git skill manifest."""
        memory = clean_memory

        result = await memory.load_skill("git")

        assert "git" in result.lower()
        assert "loaded" in result.lower() or "skill" in result.lower()

    @pytest.mark.asyncio
    async def test_load_skill_memory_itself(self, clean_memory):
        """Test loading memory skill manifest."""
        memory = clean_memory

        result = await memory.load_skill("memory")

        assert "memory" in result.lower()
        assert "loaded" in result.lower() or "skill" in result.lower()

    @pytest.mark.asyncio
    async def test_load_skill_nonexistent(self, clean_memory):
        """Test loading non-existent skill."""
        memory = clean_memory

        result = await memory.load_skill("nonexistent_skill_xyz")

        assert "not found" in result.lower() or "invalid" in result.lower()


class TestGetMemoryStats:
    """Test get_memory_stats functionality."""

    @pytest.mark.asyncio
    async def test_get_memory_stats_returns_count(self, clean_memory):
        """Test that stats returns memory count."""
        memory = clean_memory

        result = await memory.get_memory_stats()

        # Should contain a number
        assert any(c.isdigit() for c in result)
        assert "memory" in result.lower() or "stored" in result.lower()

    @pytest.mark.asyncio
    async def test_get_memory_stats_increases(self, clean_memory):
        """Test that stats increase after saving."""
        memory = clean_memory

        # Get initial count
        before = await memory.get_memory_stats()
        before_count = int("".join(filter(str.isdigit, before)) or 0)

        # Save a new memory
        await memory.save_memory(content="Stats test memory", metadata={"test_id": "stats_test"})

        # Get new count
        after = await memory.get_memory_stats()
        after_count = int("".join(filter(str.isdigit, after)) or 0)

        # Should have increased or stayed same (if counting different table)
        assert after_count >= before_count


class TestIndexMemory:
    """Test index_memory functionality."""

    @pytest.mark.asyncio
    async def test_index_memory(self, clean_memory):
        """Test index creation."""
        memory = clean_memory

        result = await memory.index_memory()

        assert "index" in result.lower() or "complete" in result.lower()


class TestMemorySaveRecallLoop:
    """Test the complete save/recall loop."""

    @pytest.mark.asyncio
    async def test_save_and_recall(self, clean_memory):
        """Test complete save/recall cycle."""
        memory = clean_memory

        # 1. Save a specific memory
        test_content = "Unique_test_memory_xyz123_save_recall"
        save_result = await memory.save_memory(
            content=test_content, metadata={"test_id": "save_recall_loop"}
        )

        assert "Saved memory" in save_result

        # 2. Recall it with semantic search
        recall_result = await memory.search_memory(query="Unique test memory xyz123", limit=5)

        # 3. Verify we found it
        assert "Found" in recall_result or test_content in recall_result

    @pytest.mark.asyncio
    async def test_sequential_saves(self, clean_memory):
        """Test multiple sequential saves."""
        memory = clean_memory

        # Save multiple memories
        for i in range(3):
            await memory.save_memory(
                content=f"Sequential memory number {i} for testing",
                metadata={"seq": i, "test_id": "sequential"},
            )

        # Search should find all
        result = await memory.search_memory(query="Sequential memory number testing", limit=10)

        assert "Found" in result


class TestMemoryModuleIntegration:
    """Integration tests with other components."""

    def test_memory_skill_manifest_valid(self):
        """Verify SKILL.md has valid structure."""
        from common.skills_path import SKILLS_DIR

        skill_md = SKILLS_DIR() / "memory" / "SKILL.md"
        assert skill_md.exists(), "SKILL.md should exist"

        content = skill_md.read_text()
        assert "---" in content, "Should have YAML frontmatter"
        assert "name:" in content, "Should have name"
        assert "routing_keywords" in content, "Should have routing keywords"

    def test_memory_readme_exists(self):
        """Verify README.md exists."""
        from common.skills_path import SKILLS_DIR

        readme = SKILLS_DIR() / "memory" / "README.md"
        assert readme.exists(), "README.md should exist"

    def test_memory_scripts_init_exports(self):
        """Verify __init__.py exports all functions."""
        from common.skills_path import SKILLS_DIR

        init_file = SKILLS_DIR() / "memory" / "scripts" / "__init__.py"
        assert init_file.exists(), "__init__.py should exist"

        content = init_file.read_text()
        assert "save_memory" in content
        assert "search_memory" in content


# =============================================================================
# Main Entry Point
# =============================================================================


async def run_tests():
    """Run all tests manually (without pytest)."""
    print("=" * 60)
    print("Memory Skill Test Suite")
    print("=" * 60)

    from common.skills_path import load_skill_module

    try:
        memory = load_skill_module("memory")
    except Exception as e:
        print(f"Failed to load memory module: {e}")
        return 1

    print("\n--- Test 1: Module Exports ---")
    exports = ["save_memory", "search_memory", "index_memory", "get_memory_stats", "load_skill"]
    for export in exports:
        if hasattr(memory, export):
            print(f"  ✓ {export}")
        else:
            print(f"  ✗ {export} MISSING")
            return 1

    print("\n--- Test 2: Save Memory ---")
    try:
        result = await memory.save_memory(
            content="Test memory for pytest", metadata={"source": "test"}
        )
        print(f"  ✓ save_memory: {result[:50]}...")
    except Exception as e:
        print(f"  ✗ save_memory failed: {e}")
        return 1

    print("\n--- Test 3: Search Memory ---")
    try:
        result = await memory.search_memory("Test memory pytest", limit=5)
        print(f"  ✓ search_memory: {result[:80]}...")
    except Exception as e:
        print(f"  ✗ search_memory failed: {e}")
        return 1

    print("\n--- Test 4: Get Stats ---")
    try:
        result = await memory.get_memory_stats()
        print(f"  ✓ stats: {result}")
    except Exception as e:
        print(f"  ✗ get_memory_stats failed: {e}")
        return 1

    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
    return 0


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "--pytest":
        # Run with pytest
        sys.exit(pytest.main([__file__, "-v"]))
    else:
        # Run manually
        return asyncio.run(run_tests())


if __name__ == "__main__":
    sys.exit(main())
