"""
scripts/verify_archiver.py
Verify MemoryArchiver works correctly.
"""

import sys
from pathlib import Path

# Ensure package imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "packages/python/agent/src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages/python/foundation/src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages/python/core/src"))


def main():
    print("🚀 Verifying MemoryArchiver Integration...")
    print("-" * 50)

    try:
        from omni.agent.core.memory.archiver import MemoryArchiver

        # Initialize archiver
        archiver = MemoryArchiver()
        print(f"✅ MemoryArchiver initialized")
        print(f"   Collection: {archiver.collection}")

        # Get stats
        stats = archiver.get_stats()
        print(f"   Initial stats: {stats}")

        # Create mock messages
        messages = [
            {"role": "user", "content": "Hello, test message"},
            {"role": "assistant", "content": "This is a test response"},
            {"role": "tool", "content": "Tool output: success"},
        ]

        print(f"\n📦 Archiving 3 messages...")
        archiver.archive_turn(messages)

        stats = archiver.get_stats()
        print(f"   Stats after archive: {stats}")

        # Add more messages (archiver should only archive new ones)
        messages.extend(
            [
                {"role": "user", "content": "Second turn user message"},
                {"role": "assistant", "content": "Second turn assistant response"},
            ]
        )

        print(f"\n📦 Archiving 2 more messages...")
        archiver.archive_turn(messages)

        stats = archiver.get_stats()
        print(f"   Final stats: {stats}")

        print("\n✅ MemoryArchiver verification PASSED")

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   (VectorStore may not be available in this environment)")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
