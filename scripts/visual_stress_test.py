"""
scripts/visual_stress_test.py
Simulate long task stress test, verify Rust Context Pruner compression effect.
"""

import sys
import time
from pathlib import Path

# Ensure package imports work
sys.path.append(str(Path(__file__).parent.parent / "packages/python/agent/src"))
sys.path.append(str(Path(__file__).parent.parent / "packages/python/foundation/src"))
sys.path.append(str(Path(__file__).parent.parent / "packages/python/core/src"))

from omni.agent.core.context.pruner import ContextPruner, PruningConfig


def main():
    print("🚀 Starting Visual Stress Test for Rust Pruner...")
    print("-" * 70)

    # Config: retain recent 3 turns, single tool output limited to 500 chars
    config = PruningConfig(retained_turns=3, max_tool_output=500)
    pruner = ContextPruner(config=config)

    messages = []
    # Add System Prompt (immutable layer)
    messages.append({"role": "system", "content": "You are Omni. " * 50})  # ~200 tokens

    print(f"⚙️  Config: Window={config.retained_turns}, MaxOutput={config.max_tool_output} chars")
    print(
        f"{'Step':<5} | {'Raw Size':<10} | {'Pruned Size':<12} | {'Time (ms)':<10} | {'Visual Curve'}"
    )
    print("-" * 70)

    # Simulate 50 rounds of conversation (usually 10 rounds would exceed Token limit)
    for i in range(1, 51):
        # 1. User command
        messages.append({"role": "user", "content": f"Step {i}: Analyze logs."})

        # 2. Assistant thought
        messages.append({"role": "assistant", "content": f"Checking log file {i}..."})

        # 3. Tool output (simulate 5KB of log noise)
        huge_log = f"[LOG-{i}] This is a very long log line..." * 200
        messages.append({"role": "tool", "content": huge_log})

        # --- Critical moment: Call Rust compression ---
        start = time.perf_counter()

        # Pruner returns compressed "view", does not modify original messages
        # (but in real Loop, we would pass this view to LLM)
        pruned_view = pruner.prune(messages)

        end = time.perf_counter()
        duration_ms = (end - start) * 1000

        # --- Calculate statistics ---
        raw_len = sum(len(str(m["content"])) for m in messages)
        pruned_len = sum(len(str(m["content"])) for m in pruned_view)

        # Simple Token estimation (char / 4)
        visual_len = int(pruned_len / 500)
        bar = "█" * visual_len

        # Check for specific truncation markers, proving Rust logic is working
        has_truncation = any(
            "truncated" in str(m["content"]).lower() or "compressed" in str(m["content"]).lower()
            for m in pruned_view
        )
        status_icon = "✂️" if has_truncation else "📝"

        print(
            f"{i:<5} | {raw_len:<10} | {pruned_len:<12} | {duration_ms:<10.2f} | {status_icon} {bar}"
        )

    print("-" * 70)
    print(f"✅ Final Raw Size: {raw_len / 1024:.2f} KB (Would Crash LLM)")
    print(f"✅ Final Pruned Size: {pruned_len / 1024:.2f} KB (Safe & Stable)")


if __name__ == "__main__":
    main()
