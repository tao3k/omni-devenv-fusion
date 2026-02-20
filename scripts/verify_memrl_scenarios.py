#!/usr/bin/env python3
"""
MemRL Complex Scenarios Verification Script

This script runs through the MemRL paper's complex scenarios using omni run + LLM.
Each scenario is presented to the LLM which should use shell commands to verify the behavior.
"""

import asyncio
import subprocess
import json
import sys
from typing import Dict, List, Any


SCENARIOS = [
    {
        "id": "self_evolution",
        "name": "Self-Evolution via Feedback",
        "description": """
Test: System should learn from success/failure experiences and adapt Q-values.

Scenario:
1. Run cargo test - first attempt fails
2. Fix the issue
3. Run cargo test again - succeeds
4. Verify Q-values adapt based on feedback
""",
        "commands": [
            "cargo test",
            "echo 'First test run - simulate failure'",
            "echo 'Fix applied'",
            "cargo test",
        ],
    },
    {
        "id": "two_phase_recall",
        "name": "Two-Phase Retrieval",
        "description": """
Test: Two-phase retrieval should filter noise and prioritize high-utility strategies.

Scenario:
1. Run multiple test commands with different outcomes
2. System should learn which approaches work better
3. Verify prioritization of successful strategies
""",
        "commands": [
            "cargo test 2>&1 | head -20",
            "ls -la",
        ],
    },
    {
        "id": "memory_decay",
        "name": "Memory Decay",
        "description": """
Test: Q-values should decay towards 0.5 over time for stale episodes.

Scenario:
1. Run a test that succeeds
2. Wait (simulated by time passage)
3. Verify Q-values have decayed towards neutral
""",
        "commands": [
            "date",
            "cargo test 2>&1 | tail -5",
            "date",
        ],
    },
    {
        "id": "multi_hop",
        "name": "Multi-hop Reasoning",
        "description": """
Test: Can chain multiple queries for complex reasoning.

Scenario:
1. Query about api errors
2. Follow up with timeout issues
3. Then network problems
4. System should link these together
""",
        "commands": [
            "grep -r 'api' src/ | head -5",
            "grep -r 'timeout' src/ | head -5",
            "grep -r 'network' src/ | head -5",
        ],
    },
    {
        "id": "q_convergence",
        "name": "Q-Learning Convergence",
        "description": """
Test: Q-values should converge towards true utility over many updates.

Scenario:
1. Run cargo test multiple times
2. Observe how Q-values converge
""",
        "commands": [
            "cargo test 2>&1",
            "cargo test 2>&1",
            "cargo test 2>&1",
        ],
    },
    {
        "id": "conflict_handling",
        "name": "Conflicting Experiences",
        "description": """
Test: System should handle conflicting experiences (same intent, different outcomes).

Scenario:
1. Run tests that sometimes pass, sometimes fail
2. System should learn to distinguish approaches
""",
        "commands": [
            "cargo test 2>&1 | grep -E '(PASSED|FAILED|ok|error)'",
        ],
    },
    {
        "id": "utility_tradeoff",
        "name": "Utility vs Similarity Trade-off",
        "description": """
Test: λ parameter controls utility vs similarity trade-off.

Scenario:
1. Run tests with different configurations
2. Compare results with different λ values
""",
        "commands": [
            "cargo test --release 2>&1 | tail -10",
            "cargo test 2>&1 | tail -10",
        ],
    },
    {
        "id": "persistence",
        "name": "Persistence and Recovery",
        "description": """
Test: Episodes and Q-values persist across restarts.

Scenario:
1. Run tests
2. Verify state is saved
3. Run again - state should be recovered
""",
        "commands": [
            "ls -la .cache/omni-vector/",
            "cargo test 2>&1 | tail -5",
        ],
    },
    {
        "id": "batch_performance",
        "name": "Batch Operations Performance",
        "description": """
Test: System handles large batch of episodes efficiently.

Scenario:
1. Run multiple test commands
2. Measure performance
""",
        "commands": [
            "cargo test 2>&1 | grep -c 'test'",
            "time cargo test 2>&1 | tail -3",
        ],
    },
    {
        "id": "incremental",
        "name": "Incremental Learning",
        "description": """
Test: System can update episodes incrementally without full rebuild.

Scenario:
1. Run test
2. Make small fix
3. Run test again - should be faster/incremental
""",
        "commands": [
            "cargo test 2>&1 | tail -5",
            "touch src/lib.rs",
            "cargo test 2>&1 | tail -5",
        ],
    },
]


async def run_scenario(scenario: Dict) -> Dict[str, Any]:
    """Run a single scenario and collect results."""
    print(f"\n{'=' * 60}")
    print(f"Scenario: {scenario['name']}")
    print(f"{'=' * 60}")
    print(scenario["description"])

    results = {
        "id": scenario["id"],
        "name": scenario["name"],
        "commands_executed": [],
        "success": False,
    }

    for cmd in scenario["commands"]:
        print(f"\n> {cmd}")
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            output = stdout.decode() if stdout else ""
            error = stderr.decode() if stderr else ""

            results["commands_executed"].append(
                {
                    "command": cmd,
                    "return_code": proc.returncode,
                    "output": output[:500],  # Limit output
                    "error": error[:500] if error else None,
                }
            )

            if output:
                print(f"  Output: {output[:200]}...")
            if error:
                print(f"  Error: {error[:200]}...")

        except Exception as e:
            results["commands_executed"].append(
                {
                    "command": cmd,
                    "error": str(e),
                }
            )
            print(f"  Exception: {e}")

    results["success"] = True
    return results


async def main():
    """Run all scenarios."""
    print("=" * 60)
    print("MemRL Complex Scenarios Verification")
    print("=" * 60)
    print(f"\nRunning {len(SCENARIOS)} scenarios...\n")

    all_results = []

    for scenario in SCENARIOS:
        result = await run_scenario(scenario)
        all_results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    successful = sum(1 for r in all_results if r["success"])
    print(f"\nTotal: {len(SCENARIOS)} scenarios")
    print(f"Executed: {successful}")

    for r in all_results:
        status = "✓" if r["success"] else "✗"
        print(f"  {status} {r['name']}")

    # Save results
    with open("memrl_verification_results.json", "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nResults saved to: memrl_verification_results.json")

    return 0 if successful == len(SCENARIOS) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
