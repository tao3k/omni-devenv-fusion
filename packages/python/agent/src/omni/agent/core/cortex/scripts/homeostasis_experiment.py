#!/usr/bin/env python3
"""
homeostasis_experiment.py - Project Homeostasis Experiment

Demonstrates:
1. TransactionShield for Git branch isolation
2. Conflict detection between concurrent tasks
3. Safe commit/rollback workflow

Usage:
    python homeostasis_experiment.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from omni.agent.core.cortex import (
    TaskGraph,
    TaskGroup,
    TaskNode,
    TaskPriority,
    TransactionShield,
    TransactionStatus,
    ConflictDetector,
    Homeostasis,
    HomeostasisConfig,
)


async def demo_transaction_shield():
    """Demonstrate TransactionShield for isolated branches."""
    print("=" * 60)
    print("Homeostasis Experiment: Transaction Shield")
    print("=" * 60)

    shield = TransactionShield(base_branch="main")

    # Simulate task transactions
    task_ids = ["task_refactor_a", "task_refactor_b", "task_test_c"]

    print("\n📦 Creating isolated transactions...")
    for task_id in task_ids:
        transaction = await shield.begin_transaction(task_id)
        print(f"   {task_id}: {transaction.branch_name} [{transaction.status.value}]")

    # Simulate recording modifications
    print("\n📝 Recording modifications...")
    await shield.record_modification(
        "task_refactor_a",
        "src/module_a.py",
        old_content="def old_func(): pass",
        new_content="def new_func(): pass",
    )
    print("   Recorded: task_refactor_a → src/module_a.py")

    await shield.record_modification(
        "task_refactor_b",
        "src/module_b.py",
        old_content="CONSTANT = 1",
        new_content="CONSTANT = 42",
    )
    print("   Recorded: task_refactor_b → src/module_b.py")

    # Show transaction summary
    print("\n📊 Transaction Summary:")
    for task_id, transaction in shield.get_all_transactions().items():
        print(f"   {task_id}:")
        print(f"      Branch: {transaction.branch_name}")
        print(f"      Status: {transaction.status.value}")
        print(f"      Files: {len([k for k in transaction.changes if k != '_commit'])}")

    # Cleanup
    print("\n🧹 Cleaning up transactions...")
    cleaned = await shield.cleanup_all()
    print(f"   Rolled back {cleaned} transactions")

    return True


async def demo_conflict_detection():
    """Demonstrate ConflictDetector for semantic conflicts."""
    print("\n" + "=" * 60)
    print("Homeostasis Experiment: Conflict Detection")
    print("=" * 60)

    detector = ConflictDetector()

    # Simulate symbols from branch A (modified function signature)
    symbols_a = {
        "functions": {
            "connect": {"signature": "def connect(host: str) -> bool", "return_type": "bool"},
        },
        "classes": {
            "Database": {
                "attributes": {
                    "connection": {"type": "Connection"},
                    "timeout": {"type": "int"},
                }
            }
        },
        "imports": ["from database import Connection"],
    }

    # Simulate symbols from branch B (calls old signature)
    symbols_b = {
        "functions": {
            "connect": {
                "signature": "def connect(url: str, timeout: int) -> Connection",
                "return_type": "Connection",
            },
        },
        "classes": {},
        "imports": ["from database import Connection", "from typing import Optional"],
    }

    # Record symbols
    detector.record_symbols("branch_a", symbols_a)
    detector.record_symbols("branch_b", symbols_b)

    # Detect conflicts
    print("\n🔍 Detecting conflicts between branches...")
    report = detector.detect_conflicts("branch_a", "branch_b")

    print(f"\n   Has Conflicts: {report.has_conflicts}")
    print(f"   Severity: {report.severity.value}")
    print(f"   Conflicts Found: {len(report.conflicts)}")

    if report.conflicts:
        for conflict in report.conflicts:
            print(f"\n   ⚠️  {conflict['type']}:")
            if conflict["type"] == "function_signature":
                print(f"      Function: {conflict['symbol']}")
                print(f"      Branch A: {conflict['branch_a']}")
                print(f"      Branch B: {conflict['branch_b']}")

    if report.suggestions:
        print("\n💡 Suggestions:")
        for suggestion in report.suggestions:
            print(f"   - {suggestion}")

    return report


async def demo_homeostasis_execution():
    """Demonstrate Homeostasis with simulated execution."""
    print("\n" + "=" * 60)
    print("Homeostasis Experiment: Full Execution")
    print("=" * 60)

    # Create a task graph
    graph = TaskGraph(name="homeostasis_demo")

    # Group 1: Two independent tasks (can run in parallel)
    group_parallel = TaskGroup(
        id="group_parallel",
        name="Parallel Tasks",
        execute_in_parallel=True,
        max_concurrent=2,
    )

    task1 = TaskNode(
        id="task_update_config",
        description="Update configuration constants",
        command="echo 'Updated CONFIG values'",
        priority=TaskPriority.HIGH,
        metadata={"file": "config.yaml", "type": "config_update"},
    )
    group_parallel.add_task(task1)

    task2 = TaskNode(
        id="task_add_logging",
        description="Add logging statements",
        command="echo 'Added logging'",
        priority=TaskPriority.MEDIUM,
        metadata={"file": "main.py", "type": "logging"},
    )
    group_parallel.add_task(task2)

    # Group 2: Verification (runs after parallel tasks)
    group_verify = TaskGroup(
        id="group_verify",
        name="Verification",
        execute_in_parallel=False,
    )

    task3 = TaskNode(
        id="task_run_tests",
        description="Run test suite",
        command="echo 'Tests passed'",
        priority=TaskPriority.CRITICAL,
        dependencies=["task_update_config", "task_add_logging"],
        metadata={"file": "tests/", "type": "testing"},
    )
    group_verify.add_task(task3)

    graph.add_group(group_parallel)
    graph.add_group(group_verify)

    print("\n📊 Task Graph:")
    print(f"   Tasks: {len(graph.all_tasks)}")
    print(f"   Groups: {len(graph.groups)}")
    print(f"   Execution Levels: {len(graph.get_execution_levels())}")

    # Create Homeostasis with simulated mode (no actual Git)
    config = HomeostasisConfig(
        enable_isolation=False,  # Disable actual Git for demo
        enable_conflict_detection=True,
        auto_merge_on_success=False,
        auto_rollback_on_failure=True,
    )

    homeostasis = Homeostasis(config=config)

    # Simulate conflict detection between parallel tasks
    print("\n🔍 Checking for conflicts...")
    detector = ConflictDetector()

    # Simulate different files being modified
    detector.record_symbols("task_update_config", {"files": ["config.yaml"]})
    detector.record_symbols("task_add_logging", {"files": ["main.py"]})

    report = detector.detect_conflicts("task_update_config", "task_add_logging")
    print(f"   Conflict Check: {report.severity.value}")

    if not report.has_conflicts:
        print("   ✅ No conflicts detected - parallel execution safe")

    # Show execution plan
    print("\n📋 Execution Plan:")
    levels = graph.get_execution_levels()
    for i, level in enumerate(levels):
        print(f"   Level {i}: {level}")

    print("\n✅ Homeostasis configuration validated")

    return True


async def demo_transaction_status_machine():
    """Demonstrate transaction status state machine."""
    print("\n" + "=" * 60)
    print("Homeostasis Experiment: Transaction Lifecycle")
    print("=" * 60)

    shield = TransactionShield()

    # Create a transaction
    print("\n🔄 Transaction Lifecycle Simulation:")
    print()

    # Simulate lifecycle
    lifecycle = [
        ("Created", TransactionStatus.IDLE),
        ("Preparing", TransactionStatus.PREPARING),
        ("Isolated", TransactionStatus.ISOLATED),
        ("Modifying", TransactionStatus.MODIFYING),
        ("Committed", TransactionStatus.COMMITTED),
        ("Verified", TransactionStatus.VERIFIED),
        ("Merged", TransactionStatus.MERGED),
    ]

    for name, status in lifecycle:
        print(f"   {name:12} → {status.value}")

    print("\n   ✅ Full lifecycle demonstrated")

    return True


async def main():
    """Run all Homeostasis experiments."""
    print("\n🏠 Project Homeostasis Experiments")
    print("=" * 60)

    results = []

    # Demo 1: Transaction Shield
    try:
        success = await demo_transaction_shield()
        results.append(("Transaction Shield", success))
    except Exception as e:
        print(f"\n❌ Transaction Shield Failed: {e}")
        results.append(("Transaction Shield", False))

    # Demo 2: Conflict Detection
    try:
        success = await demo_conflict_detection()
        results.append(("Conflict Detection", success))
    except Exception as e:
        print(f"\n❌ Conflict Detection Failed: {e}")
        results.append(("Conflict Detection", False))

    # Demo 3: Full Homeostasis Execution
    try:
        success = await demo_homeostasis_execution()
        results.append(("Homeostasis Execution", success))
    except Exception as e:
        print(f"\n❌ Homeostasis Execution Failed: {e}")
        results.append(("Homeostasis Execution", False))

    # Demo 4: Transaction Lifecycle
    try:
        success = await demo_transaction_status_machine()
        results.append(("Transaction Lifecycle", success))
    except Exception as e:
        print(f"\n❌ Transaction Lifecycle Failed: {e}")
        results.append(("Transaction Lifecycle", False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Experiment Summary")
    print("=" * 60)
    for name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"   {name}: {status}")

    all_passed = all(r[1] for r in results)
    print("\n" + ("✅ All experiments passed!" if all_passed else "❌ Some experiments failed"))

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
