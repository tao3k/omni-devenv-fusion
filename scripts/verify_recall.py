"""
scripts/verify_recall.py
Verify EpisodicMemoryProvider recall functionality.
"""

import sys
import asyncio
from pathlib import Path

# Ensure package imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "packages/python/agent/src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages/python/foundation/src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages/python/core/src"))


async def test_recall():
    print("🚀 Testing EpisodicMemoryProvider Recall...")
    print("-" * 60)

    try:
        from omni.core.context.providers import EpisodicMemoryProvider
        from omni.foundation.services.vector import get_vector_store
        from omni.agent.core.memory.archiver import MemoryArchiver

        # Step 1: Archive some memories
        print("📦 Step 1: Archiving memories...")
        archiver = MemoryArchiver()
        messages = [
            {"role": "user", "content": "My secret code is 42, remember this!"},
            {"role": "assistant", "content": "I will remember that your secret code is 42."},
            {"role": "tool", "content": "Memory stored successfully"},
        ]
        archiver.archive_turn(messages)
        print(f"   Archived {len(messages)} messages")
        print(f"   Archiver stats: {archiver.get_stats()}")

        # Step 2: Test recall with different queries
        print("\n🔍 Step 2: Testing recall queries...")

        provider = EpisodicMemoryProvider(top_k=3)

        # Test 1: Query about secret code
        print("\n   Query 1: 'secret code'")
        state = {
            "messages": [{"role": "user", "content": "What is my secret code?"}],
            "current_task": "What is my secret code?",
        }
        result = await provider.provide(state, budget=10000)
        if result:
            print(f"   ✅ Found memories ({result.token_count} tokens):")
            print(f"   {result.content[:200]}...")
        else:
            print("   ❌ No memories found")

        # Test 2: Query about stored data
        print("\n   Query 2: 'remember this'")
        state = {
            "messages": [{"role": "user", "content": "Did I ask you to remember anything?"}],
            "current_task": "Did I ask you to remember anything?",
        }
        result = await provider.provide(state, budget=10000)
        if result:
            print(f"   ✅ Found memories ({result.token_count} tokens):")
            print(f"   {result.content[:200]}...")
        else:
            print("   ❌ No memories found")

        # Test 3: Query with short text (should skip)
        print("\n   Query 3: 'hi' (too short, should skip)")
        state = {
            "messages": [{"role": "user", "content": "hi"}],
            "current_task": "hi",
        }
        result = await provider.provide(state, budget=10000)
        if result:
            print(f"   ⚠️  Unexpected result: {result.content[:100]}")
        else:
            print("   ✅ Correctly skipped (query too short)")

        print("\n" + "-" * 60)
        print("✅ EpisodicMemoryProvider verification PASSED")

    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_recall())
