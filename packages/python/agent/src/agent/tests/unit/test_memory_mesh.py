#!/usr/bin/env python3
"""
agent/tests/unit/test_memory_mesh.py
Phase 71: The Memory Mesh - Test Script

Tests the episodic memory system:
1. Writing experiences
2. Retrieving memories
3. Memory integration with AdaptiveLoader

Usage:
    python3 -m agent.tests.unit.test_memory_mesh
"""

import asyncio
import sys
from pathlib import Path


async def test_memory_types():
    """Test InteractionLog data model."""
    print("=== Test 1: Memory Types ===")

    from agent.core.memory.types import InteractionLog

    # Create a log
    log = InteractionLog(
        user_query="git commit fails due to lock file",
        tool_calls=["git.commit", "file.delete"],
        outcome="failure",
        error_msg="fatal: Unable to create '.git/index.lock': File exists.",
        reflection="Git lock error solved by removing .git/index.lock file before retrying.",
    )

    print(f"  ID: {log.id[:8]}...")
    print(f"  Timestamp: {log.timestamp}")
    print(f"  Query: {log.user_query[:40]}...")
    print(f"  Outcome: {log.outcome}")
    print(f"  Reflection: {log.reflection[:50]}...")

    # Test vector record conversion
    record = log.to_vector_record()
    print(f"  Vector record keys: {list(record.keys())}")

    assert log.id, "ID should be generated"
    assert log.timestamp, "Timestamp should be set"
    assert log.outcome == "failure", "Outcome should be failure"
    assert "text" in record, "Vector record should have text field"

    print("  ✓ Types test passed\n")
    return True


async def test_memory_manager():
    """Test Memory Manager operations."""
    print("=== Test 2: Memory Manager ===")

    from agent.core.memory.manager import get_memory_manager

    mm = get_memory_manager()

    # Test 1: Add experience (success)
    print("  Adding success experience...")
    success_id = await mm.add_experience(
        user_query="Create a new Python file with hello world",
        tool_calls=["file.create"],
        outcome="success",
        reflection="File created successfully at /path/to/hello.py",
    )
    print(f"    Created: {success_id[:8] if success_id else 'FAILED'}...")

    # Test 2: Add experience (failure)
    print("  Adding failure experience...")
    fail_id = await mm.add_experience(
        user_query="git commit fails due to lock file",
        tool_calls=["git.commit"],
        outcome="failure",
        error_msg="fatal: Unable to create '.git/index.lock': File exists.",
        reflection="Git lock error solved by removing .git/index.lock file before retrying.",
    )
    print(f"    Created: {fail_id[:8] if fail_id else 'FAILED'}...")

    # Test 3: Recall memories
    print("  Recalling memories about git commit...")
    memories = await mm.recall("git commit lock file", limit=5)
    print(f"    Found {len(memories)} memories")

    for m in memories:
        status = "✓" if m.outcome == "success" else "✗"
        print(f"    [{status}] {m.reflection[:60]}...")

    # Test 4: Get count
    count = await mm.count()
    print(f"  Total memories: {count}")

    assert success_id, "Should create success memory"
    assert fail_id, "Should create failure memory"
    assert len(memories) > 0, "Should find some memories"

    print("  ✓ Manager test passed\n")
    return True


async def test_memory_interceptor():
    """Test Memory Interceptor."""
    print("=== Test 3: Memory Interceptor ===")

    from agent.core.memory.interceptor import get_memory_interceptor

    interceptor = get_memory_interceptor()

    # Test before_execution
    print("  Testing before_execution...")
    memories = await interceptor.before_execution("git commit issues")
    print(f"    Found {len(memories)} relevant memories")

    # Test after_execution (success)
    print("  Testing after_execution (success)...")
    record_id = await interceptor.after_execution(
        user_input="Create a test file",
        tool_calls=["file.create"],
        success=True,
    )
    print(f"    Recorded: {record_id[:8] if record_id else 'FAILED'}...")

    # Test after_execution (failure)
    print("  Testing after_execution (failure)...")
    record_id = await interceptor.after_execution(
        user_input="Delete non-existent file",
        tool_calls=["file.delete"],
        success=False,
        error="FileNotFoundError: No such file",
    )
    print(f"    Recorded: {record_id[:8] if record_id else 'FAILED'}...")

    print("  ✓ Interceptor test passed\n")
    return True


async def test_adaptive_loader_integration():
    """Test AdaptiveLoader memory methods."""
    print("=== Test 4: AdaptiveLoader Integration ===")

    from agent.core.adaptive_loader import get_adaptive_loader

    loader = get_adaptive_loader()

    # Test get_relevant_memories
    print("  Testing get_relevant_memories...")
    memory_context = await loader.get_relevant_memories("git commit error", limit=3)
    print(f"    Context length: {len(memory_context)} chars")

    if memory_context:
        print(f"    Preview: {memory_context[:100]}...")
    else:
        print("    (No memories found)")

    # Test record_experience
    print("  Testing record_experience...")
    record_id = await loader.record_experience(
        user_query="Test memory recording",
        tool_calls=["test.tool"],
        success=True,
    )
    print(f"    Recorded: {record_id[:8] if record_id else 'FAILED'}...")

    print("  ✓ AdaptiveLoader integration test passed\n")
    return True


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Phase 71: The Memory Mesh - Test Suite")
    print("=" * 60 + "\n")

    all_passed = True

    try:
        await test_memory_types()
    except Exception as e:
        print(f"  ✗ Types test failed: {e}\n")
        all_passed = False

    try:
        await test_memory_manager()
    except Exception as e:
        print(f"  ✗ Manager test failed: {e}\n")
        all_passed = False

    try:
        await test_memory_interceptor()
    except Exception as e:
        print(f"  ✗ Interceptor test failed: {e}\n")
        all_passed = False

    try:
        await test_adaptive_loader_integration()
    except Exception as e:
        print(f"  ✗ AdaptiveLoader test failed: {e}\n")
        all_passed = False

    print("=" * 60)
    if all_passed:
        print("All tests passed! ✓")
    else:
        print("Some tests failed! ✗")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
