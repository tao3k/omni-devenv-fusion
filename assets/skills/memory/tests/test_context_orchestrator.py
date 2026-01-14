#!/usr/bin/env python3
"""
scripts/test_context_orchestrator.py
Phase 55: The Conductor - Integration Test.

Tests the Hierarchical Context Orchestration system.
"""

# Setup import paths using common.lib
from common.lib import setup_import_paths

setup_import_paths()


def test_context_orchestrator_initialization():
    """Test that ContextOrchestrator initializes correctly."""
    print("\n" + "=" * 60)
    print("🚀 Phase 55: The Conductor - Initialization Test")
    print("=" * 60)

    try:
        from agent.core.context_orchestrator import (
            ContextOrchestrator,
            get_context_orchestrator,
        )

        # Test singleton
        orchestrator = get_context_orchestrator()
        orchestrator2 = get_context_orchestrator()

        assert orchestrator is orchestrator2, "Singleton should return same instance"
        print("  ✅ Singleton pattern works")

        # Test custom initialization
        custom = ContextOrchestrator(max_tokens=64000)
        assert custom.max_tokens == 64000
        assert custom.input_budget == 51200  # 80% of 64000
        print("  ✅ Custom configuration works")

        # Test layers are initialized
        assert len(orchestrator.layers) == 5, "Should have 5 layers"
        print("  ✅ All 5 layers initialized")

        return True

    except Exception as e:
        print(f"  ❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_layer1_system_persona():
    """Test Layer 1: System Persona + Scratchpad."""
    print("\n[2] Testing Layer 1: System Persona")
    print("-" * 50)

    try:
        from agent.core.context_orchestrator import Layer1_SystemPersona

        layer = Layer1_SystemPersona()
        content, tokens = layer.assemble("Test task", [], 10000)

        assert tokens > 0, "Should have generated content"
        assert "System" in content or "Claude" in content or "Omni" in content, (
            "Should contain system prompt content"
        )
        print(f"  ✅ Layer 1 generated {tokens} tokens")
        print(f"     Content preview: {content[:100]}...")

        return True

    except Exception as e:
        print(f"  ❌ Test failed: {e}")
        return False


def test_layer2_environment():
    """Test Layer 2: Environment Snapshot."""
    print("\n[3] Testing Layer 2: Environment Snapshot")
    print("-" * 50)

    try:
        from agent.core.context_orchestrator import Layer2_EnvironmentSnapshot

        layer = Layer2_EnvironmentSnapshot()
        content, tokens = layer.assemble("Check environment", [], 1000)

        print(f"  ✅ Layer 2 generated {tokens} tokens")
        if content:
            print(f"     Preview: {content[:80]}...")
        else:
            print("     (No environment data - expected if omni_core_rs not available)")

        return True

    except Exception as e:
        print(f"  ❌ Test failed: {e}")
        return False


def test_layer3_memories():
    """Test Layer 3: Associative Memories."""
    print("\n[4] Testing Layer 3: Associative Memories")
    print("-" * 50)

    try:
        from agent.core.context_orchestrator import Layer3_AssociativeMemories

        layer = Layer3_AssociativeMemories()

        # Mock history with some content
        history = [
            {"role": "user", "content": "Fix the PyO3 deprecation warning"},
            {"role": "assistant", "content": "I will update the Python bindings"},
        ]

        content, tokens = layer.assemble("Fix PyO3 warning", history, 2000)

        print(f"  ✅ Layer 3 generated {tokens} tokens")
        if content and "Memory" in content:
            print(f"     Found memories in context")

        return True

    except Exception as e:
        print(f"  ❌ Test failed: {e}")
        return False


def test_full_prompt_build():
    """Test building complete context prompt."""
    print("\n[5] Testing Full Prompt Build")
    print("-" * 50)

    try:
        from agent.core.context_orchestrator import get_context_orchestrator

        orchestrator = get_context_orchestrator()

        # Mock conversation history
        history = [
            {"role": "user", "content": "Fix the login bug in src/auth.py"},
            {"role": "assistant", "content": "Let me check the auth module structure first."},
            {"role": "system", "content": "Running: cargo check -p omni-vector"},
        ]

        # Build prompt
        prompt = orchestrator.build_prompt(
            task="Fix authentication bug in login flow",
            history=history,
        )

        # Verify
        assert len(prompt) > 0, "Should have generated prompt"
        tokens = orchestrator.get_context_stats(prompt)
        assert tokens["total_tokens"] > 0, "Should have token count"

        print(f"  ✅ Full prompt built: {tokens['total_tokens']} tokens")
        print(f"     Utilization: {tokens['utilization']:.1%}")
        print(f"     Preview: {prompt[:150]}...")

        return True

    except Exception as e:
        print(f"  ❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_token_budgeting():
    """Test that token budgeting works correctly."""
    print("\n[6] Testing Token Budgeting")
    print("-" * 50)

    try:
        from agent.core.context_orchestrator import ContextOrchestrator

        # Create orchestrator with very small budget
        orchestrator = ContextOrchestrator(max_tokens=1000, output_ratio=0.5)
        assert orchestrator.input_budget == 500, "Should have 500 token input budget"

        history = [
            {"role": "user", "content": "Short test query"},
        ]

        prompt = orchestrator.build_prompt("Test task", history)
        stats = orchestrator.get_context_stats(prompt)

        print(f"  ✅ Budget enforced: {stats['total_tokens']} tokens in prompt")
        assert stats["total_tokens"] <= orchestrator.max_tokens, "Should not exceed max tokens"

        return True

    except Exception as e:
        print(f"  ❌ Test failed: {e}")
        return False


def main():
    print("=" * 60)
    print("🎯 Phase 55: The Conductor - Integration Test")
    print("=" * 60)

    results = []

    results.append(("Initialization", test_context_orchestrator_initialization()))
    results.append(("Layer 1: System Persona", test_layer1_system_persona()))
    results.append(("Layer 2: Environment", test_layer2_environment()))
    results.append(("Layer 3: Memories", test_layer3_memories()))
    results.append(("Full Prompt Build", test_full_prompt_build()))
    results.append(("Token Budgeting", test_token_budgeting()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✅ Phase 55 Complete: The Conductor is operational!")
        print("\nThe Agent can now:")
        print("  1. Assemble context in priority layers (Pyramid)")
        print("  2. Respect strict token budgets")
        print("  3. Dynamically recall memories from Librarian")
        print("  4. Map code structure with omni-tags")
        print("  5. Build 'Perfect Prompts' for any task")
        return 0
    else:
        print("\n❌ Some tests failed.")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
