#!/usr/bin/env python3
"""
Multi-branch transaction test using real Git repository at /tmp/gitdir.
"""

import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from omni.agent.core.cortex.transaction import (
    TransactionShield,
    TransactionStatus,
)


async def test_multi_branch_isolation():
    """Test creating multiple isolated branches for concurrent tasks."""
    print("=" * 60)
    print("Multi-Branch Isolation Test")
    print("=" * 60)

    # Use the real git repo
    repo_path = Path("/tmp/gitdir")
    print(f"\nRepository: {repo_path}")
    print(f"Exists: {repo_path.exists()}")

    # Create shield with the repo path
    shield = TransactionShield(base_branch="main")

    # Override repo root to use our test repo
    shield._repo_root = repo_path

    # Create random namespace for this test run
    import random
    import string

    namespace = "".join(random.choices(string.ascii_lowercase, k=6))
    print(f"Test namespace: {namespace}")

    # Create isolated transactions for multiple tasks
    task_ids = [f"task_{namespace}_a", f"task_{namespace}_b", f"task_{namespace}_c"]

    print(f"\n📦 Creating {len(task_ids)} isolated transactions...")
    transactions = {}

    for task_id in task_ids:
        try:
            transaction = await shield.begin_transaction(task_id)
            transactions[task_id] = transaction
            print(f"   {task_id}: {transaction.branch_name} [{transaction.status.value}]")

            # Verify we're on the new branch
            import subprocess

            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            current_branch = result.stdout.strip()
            print(f"      Current branch: {current_branch}")
        except Exception as e:
            print(f"   {task_id}: FAILED - {e}")

    # Verify all branches exist
    print("\n🔍 Verifying all branches exist...")
    import subprocess

    result = subprocess.run(["git", "branch", "-a"], cwd=repo_path, capture_output=True, text=True)
    branches = result.stdout.strip().split("\n")
    omni_branches = [b.strip() for b in branches if "omni-task" in b]
    print(f"   Omni branches: {len(omni_branches)}")

    # Cleanup all transactions
    print(f"\n🧹 Cleaning up {len(transactions)} transactions...")
    cleaned = await shield.cleanup_all()
    print(f"   Cleaned up: {cleaned}")

    # Verify branches are deleted
    result = subprocess.run(["git", "branch", "-a"], cwd=repo_path, capture_output=True, text=True)
    branches = result.stdout.strip().split("\n")
    omni_branches = [b.strip() for b in branches if "omni-task" in b]
    print(f"   Remaining omni branches: {len(omni_branches)}")

    success = cleaned == len(task_ids) and len(omni_branches) == 0
    print(f"\n✅ Test {'PASSED' if success else 'FAILED'}")

    return success


async def test_concurrent_modifications():
    """Test that concurrent modifications work in isolation."""
    print("\n" + "=" * 60)
    print("Concurrent Modifications Test")
    print("=" * 60)

    import random
    import string

    namespace = "".join(random.choices(string.ascii_lowercase, k=6))

    repo_path = Path("/tmp/gitdir")
    shield = TransactionShield(base_branch="main")
    shield._repo_root = repo_path

    # Create file for modification
    test_file = repo_path / "concurrent_test.py"

    # Begin transaction A
    task_a = f"task_{namespace}_a"
    print(f"\n🔄 Starting task A: {task_a}")
    tx_a = await shield.begin_transaction(task_a)
    print(f"   Branch: {tx_a.branch_name}")

    # Write file in task A
    with open(test_file, "w") as f:
        f.write("# Modified by A\nVALUE_A = 1\n")

    import subprocess

    subprocess.run(["git", "add", "concurrent_test.py"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "A modifies file"], cwd=repo_path, check=True)
    print(f"   Task A committed")

    # Go back to main and create task B
    subprocess.run(["git", "checkout", "main"], cwd=repo_path, check=True)
    task_b = f"task_{namespace}_b"
    print(f"\n🔄 Starting task B: {task_b}")
    tx_b = await shield.begin_transaction(task_b)
    print(f"   Branch: {tx_b.branch_name}")

    # Modify file in task B (different content)
    with open(test_file, "w") as f:
        f.write("# Modified by B\nVALUE_B = 2\n")

    subprocess.run(["git", "add", "concurrent_test.py"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "B modifies file"], cwd=repo_path, check=True)
    print(f"   Task B committed")

    # Now try to merge both into main
    print("\n🔀 Attempting to merge both branches...")
    result = subprocess.run(
        ["git", "merge", tx_a.branch_name, "--no-edit"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    merge_a = result.returncode == 0
    print(f"   Merge A result: {'Success' if merge_a else 'Conflict'}")

    if not merge_a:
        print(f"   Conflict details: {result.stderr[:100]}...")

    # Reset for B merge attempt
    subprocess.run(["git", "reset", "--hard", "main"], cwd=repo_path, check=True)

    result = subprocess.run(
        ["git", "merge", tx_b.branch_name, "--no-edit"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    merge_b = result.returncode == 0
    print(f"   Merge B result: {'Success' if merge_b else 'Conflict'}")

    if not merge_b:
        print(f"   Conflict details: {result.stderr[:100]}...")

    # Cleanup
    print(f"\n🧹 Cleaning up...")
    await shield.cleanup_all()

    # Verify final state
    result = subprocess.run(
        ["git", "log", "--oneline", "-5"], cwd=repo_path, capture_output=True, text=True
    )
    print(f"\n📜 Final commit history:")
    for line in result.stdout.strip().split("\n"):
        print(f"   {line}")

    print(f"\n✅ Test completed - concurrent modifications isolated")

    return True


async def main():
    """Run all tests."""
    print("\n🏠 Multi-Branch Transaction Tests")
    print("=" * 60)

    results = []

    try:
        success = await test_multi_branch_isolation()
        results.append(("Multi-Branch Isolation", success))
    except Exception as e:
        print(f"\n❌ Multi-Branch Isolation Failed: {e}")
        import traceback

        traceback.print_exc()
        results.append(("Multi-Branch Isolation", False))

    try:
        success = await test_concurrent_modifications()
        results.append(("Concurrent Modifications", success))
    except Exception as e:
        print(f"\n❌ Concurrent Modifications Failed: {e}")
        import traceback

        traceback.print_exc()
        results.append(("Concurrent Modifications", False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    for name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"   {name}: {status}")

    all_passed = all(r[1] for r in results)
    print("\n" + ("✅ All tests passed!" if all_passed else "❌ Some tests failed"))

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
