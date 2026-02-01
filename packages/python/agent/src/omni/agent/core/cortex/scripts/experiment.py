#!/usr/bin/env python3
"""
experiment.py - Prefrontal Cortex Experiment

Demonstrates parallel task orchestration with:
- Task decomposition from high-level goals
- Parallel execution of independent tasks
- Dependency-aware scheduling

Usage:
    python experiment.py [--goal "Your goal here"]
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from omni.agent.core.cortex import (
    TaskGraph,
    TaskGroup,
    TaskNode,
    TaskPriority,
    CortexOrchestrator,
    ExecutionConfig,
)


async def demo_parallel_refactor():
    """Demonstrate parallel refactoring of independent modules."""
    print("=" * 60)
    print("Prefrontal Cortex Experiment: Parallel Refactoring")
    print("=" * 60)

    import tempfile
    import shutil

    # Use a temp directory for the demo
    temp_dir = Path(tempfile.mkdtemp(prefix="cortex_demo_"))
    module_a_path = temp_dir / "module_a.py"
    module_b_path = temp_dir / "module_b.py"

    try:
        # Create a task graph for refactoring two independent modules
        graph = TaskGraph(name="parallel_refactor_demo")

        # Group 1: Refactor Module A (can run in parallel with Group 2)
        group_a = TaskGroup(
            id="group_module_a",
            name="Refactor Module A",
            execute_in_parallel=True,
            max_concurrent=2,
        )

        # Task 1.1: Rename a constant in module_a.py
        task_a1 = TaskNode(
            id="task_rename_constant_a",
            description="Rename CONSTANT_A to MODULE_A_CONSTANT in module_a.py",
            command=f'sed -i "s/CONSTANT_A/MODULE_A_CONSTANT/g" {module_a_path}',
            priority=TaskPriority.HIGH,
            metadata={"file": str(module_a_path), "type": "rename"},
        )
        group_a.add_task(task_a1)

        # Task 1.2: Update imports in module_a.py
        task_a2 = TaskNode(
            id="task_update_imports_a",
            description="Update import statements in module_a.py",
            command=f'sed -i "s/from utils/from core.utils/g" {module_a_path}',
            priority=TaskPriority.MEDIUM,
            dependencies=["task_rename_constant_a"],  # Depends on previous task
            metadata={"file": str(module_a_path), "type": "import_update"},
        )
        group_a.add_task(task_a2)

        # Group 2: Refactor Module B (runs in parallel with Group 1)
        group_b = TaskGroup(
            id="group_module_b",
            name="Refactor Module B",
            execute_in_parallel=True,
            max_concurrent=2,
        )

        # Task 2.1: Rename a constant in module_b.py
        task_b1 = TaskNode(
            id="task_rename_constant_b",
            description="Rename CONSTANT_B to MODULE_B_CONSTANT in module_b.py",
            command=f'sed -i "s/CONSTANT_B/MODULE_B_CONSTANT/g" {module_b_path}',
            priority=TaskPriority.HIGH,
            metadata={"file": str(module_b_path), "type": "rename"},
        )
        group_b.add_task(task_b1)

        # Task 2.2: Update imports in module_b.py
        task_b2 = TaskNode(
            id="task_update_imports_b",
            description="Update import statements in module_b.py",
            command=f'sed -i "s/from utils/from core.utils/g" {module_b_path}',
            priority=TaskPriority.MEDIUM,
            dependencies=["task_rename_constant_b"],
            metadata={"file": str(module_b_path), "type": "import_update"},
        )
        group_b.add_task(task_b2)

        # Group 3: Verify both modules (runs after both groups complete)
        group_verify = TaskGroup(
            id="group_verify",
            name="Verify refactoring",
            execute_in_parallel=False,
        )

        task_v1 = TaskNode(
            id="task_verify_a",
            description="Verify module_a.py syntax",
            command=f"python -m py_compile {module_a_path}",
            priority=TaskPriority.CRITICAL,
            # Verify task depends on all tasks in group A
            dependencies=["task_rename_constant_a", "task_update_imports_a"],
        )
        group_verify.add_task(task_v1)

        task_v2 = TaskNode(
            id="task_verify_b",
            description="Verify module_b.py syntax",
            command=f"python -m py_compile {module_b_path}",
            priority=TaskPriority.CRITICAL,
            # Verify task depends on all tasks in group B
            dependencies=["task_rename_constant_b", "task_update_imports_b"],
        )
        group_verify.add_task(task_v2)

        # Add groups to graph
        graph.add_group(group_a)
        graph.add_group(group_b)
        graph.add_group(group_verify)

        # Print graph summary
        print("\n📊 Task Graph Summary:")
        print(f"   Total Tasks: {len(graph.all_tasks)}")
        print(f"   Total Groups: {len(graph.groups)}")
        print(f"   Execution Levels: {len(graph.get_execution_levels())}")
        print(f"   Has Cycles: {graph.detect_cycles()}")

        print("\n📋 Execution Order:")
        levels = graph.get_execution_levels()
        for i, level in enumerate(levels):
            print(f"   Level {i}: {level}")

        # Execute with CortexOrchestrator
        print("\n🚀 Executing Task Graph...")
        config = ExecutionConfig(
            max_concurrent_groups=2,
            max_concurrent_tasks=4,
            stop_on_failure=False,
        )
        orchestrator = CortexOrchestrator(config)

        # Create mock files for demonstration
        print("\n📁 Creating mock files...")
        module_a_path.write_text("""# Module A
CONSTANT_A = 42

def hello_a():
    from utils import helper
    return helper()
""")
        module_b_path.write_text("""# Module B
CONSTANT_B = 100

def hello_b():
    from utils import helper
    return helper()
""")
        print(f"   Created: {module_a_path}, {module_b_path}")

        # Execute
        result = await orchestrator.execute(graph)

        print("\n" + "=" * 60)
        print("📈 Execution Results:")
        print("=" * 60)
        print(f"   Success: {result.success}")
        print(f"   Tasks Completed: {result.completed_tasks}/{result.total_tasks}")
        print(f"   Failed: {result.failed_tasks}")
        print(f"   Duration: {result.duration_ms:.2f}ms")

        if result.metrics:
            print(
                f"   Throughput: {result.metrics.get('throughput_tasks_per_sec', 0):.2f} tasks/sec"
            )

        # Show file contents after refactoring
        print("\n📄 Refactored Files:")
        for f in [module_a_path, module_b_path]:
            if f.exists():
                content = f.read_text()
                print(f"\n--- {f.name} ---")
                print(content[:200] + "..." if len(content) > 200 else content)

        return result.success

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


async def demo_goal_decomposition():
    """Demonstrate goal decomposition."""
    print("\n" + "=" * 60)
    print("Prefrontal Cortex Experiment: Goal Decomposition")
    print("=" * 60)

    from omni.agent.core.cortex import TaskDecomposer

    decomposer = TaskDecomposer()

    # Test various goals
    goals = [
        "Rename all API endpoints to follow new naming convention",
        "Add unit tests for all functions in the auth module",
        "Create documentation for the core module",
        "Migrate from Python 3.8 to Python 3.11",
    ]

    for goal in goals:
        print(f"\n🎯 Goal: {goal}")
        result = await decomposer.decompose(goal)

        if result.success:
            print(f"   ✅ Decomposed into {len(result.task_graph.all_tasks)} tasks")
            print(f"   📊 Graph: {result.task_graph.summary()}")
        else:
            print(f"   ❌ Failed: {result.error}")

    return True


async def demo_cost_aware_reflection():
    """Demonstrate cost-aware reflection for task evaluation."""
    print("\n" + "=" * 60)
    print("Prefrontal Cortex: Cost-Aware Reflection")
    print("=" * 60)

    # Simulate cost analysis
    task_costs = [
        ("Update 1 file", 1, "low"),
        ("Update 5 files", 5, "medium"),
        ("Update 10+ files, some with dependencies", 12, "high"),
        ("Core function refactor (50+ files affected)", 50, "critical"),
    ]

    print("\n💰 Task Cost Analysis:")
    print("-" * 50)
    for task, files, level in task_costs:
        risk = "⚠️  Consider breaking into parallel tasks" if files > 5 else "✅ Safe to proceed"
        print(f"   {task}")
        print(f"   Risk Level: {level.upper()} | {risk}")
        print()

    return True


async def main():
    """Run all experiments."""
    print("\n🧠 Prefrontal Cortex Experiments")
    print("=" * 60)

    results = []

    # Demo 1: Parallel refactoring
    try:
        success = await demo_parallel_refactor()
        results.append(("Parallel Refactoring", success))
    except Exception as e:
        print(f"\n❌ Parallel Refactoring Failed: {e}")
        results.append(("Parallel Refactoring", False))

    # Demo 2: Goal decomposition
    try:
        success = await demo_goal_decomposition()
        results.append(("Goal Decomposition", success))
    except Exception as e:
        print(f"\n❌ Goal Decomposition Failed: {e}")
        results.append(("Goal Decomposition", False))

    # Demo 3: Cost-aware reflection
    try:
        success = await demo_cost_aware_reflection()
        results.append(("Cost-Aware Reflection", success))
    except Exception as e:
        print(f"\n❌ Cost-Aware Reflection Failed: {e}")
        results.append(("Cost-Aware Reflection", False))

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
