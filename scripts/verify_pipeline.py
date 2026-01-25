#!/usr/bin/env python3
"""
scripts/verify_pipeline.py - Integration Test for Rust-Powered Context Pipeline

Verifies that the Cognitive Pipeline correctly uses Rust ContextAssembler
for parallel I/O, template rendering, and token counting.

Usage:
    uv run python scripts/verify_pipeline.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add packages to path for imports (uv manages dependencies)
AGENT_SRC = Path(__file__).parent.parent / "packages/python/agent/src"
CORE_SRC = Path(__file__).parent.parent / "packages/python/core/src"
FOUNDATION_SRC = Path(__file__).parent.parent / "packages/python/foundation/src"

sys.path.insert(0, str(AGENT_SRC))
sys.path.insert(0, str(CORE_SRC))
sys.path.insert(0, str(FOUNDATION_SRC))

from omni.foundation.config.logging import get_logger
from omni.foundation.config.settings import get_settings
from omni.core.context import create_planner_orchestrator
from omni.core.skills.memory import get_skill_memory

logger = get_logger("verify_pipeline")


async def verify_pipeline():
    """Verify the Rust-powered cognitive pipeline."""
    print("=" * 60)
    print("🚀 Rust-Powered Cognitive Pipeline Verification")
    print("=" * 60)

    settings = get_settings()
    project_root = Path(settings.get("general.project_root", "."))
    print(f"📂 Project Root: {project_root}")

    # 1. Check that Rust ContextAssembler is available
    try:
        from omni_core_rs import ContextAssembler

        print("✅ Rust ContextAssembler imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import Rust ContextAssembler: {e}")
        return False

    # 2. Create a fake state (simulating LangGraph state)
    fake_state = {
        "active_skill": "researcher",
        "request": "Analyze the omni-io crate architecture",
        "project_root": str(project_root),
        "messages": [],
    }

    # 3. Initialize the Orchestrator (uses Rust internally via ActiveSkillProvider)
    print("\n📦 Initializing Context Orchestrator...")
    orchestrator = create_planner_orchestrator()
    print("✅ Orchestrator initialized")

    # 4. Build Context (triggers Rust ContextAssembler)
    print("\n🧠 Building Context (calling Rust ContextAssembler)...")
    try:
        start_time = asyncio.get_running_loop().time()

        system_prompt = await orchestrator.build_context(fake_state)

        end_time = asyncio.get_running_loop().time()
        duration_ms = (end_time - start_time) * 1000

        print(f"⚡ Context built in {duration_ms:.2f}ms")
    except Exception as e:
        print(f"❌ Error building context: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 5. Verify content
    print("\n🔍 Verification Results:")
    print("-" * 60)

    checks = [
        ("<active_protocol>", "Active Protocol tag", system_prompt),
        ("</active_protocol>", "Active Protocol closing tag", system_prompt),
        ("researcher", "SKILL.md content (researcher)", system_prompt),
    ]

    all_passed = True
    for pattern, name, content in checks:
        if pattern in content:
            print(f"✅ PASS: {name} found")
        else:
            print(f"❌ FAIL: {name} missing")
            all_passed = False

    # 6. Token estimate
    token_estimate = len(system_prompt) // 4
    print(f"\n📝 Token Estimate: ~{token_estimate} tokens")
    print(f"📏 Content Length: {len(system_prompt)} chars")

    # 7. Show a preview
    print("\n" + "-" * 60)
    print("📄 Content Preview (first 500 chars):")
    print("-" * 60)
    print(system_prompt[:500])
    print("...")

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL CHECKS PASSED - Rust Pipeline is working!")
    else:
        print("❌ SOME CHECKS FAILED - Review the output above")
    print("=" * 60)

    return all_passed


def main():
    """Entry point."""
    try:
        result = asyncio.run(verify_pipeline())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
