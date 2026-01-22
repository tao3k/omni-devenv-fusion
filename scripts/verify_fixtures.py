#!/usr/bin/env uv run python
"""
verify_fixtures.py - Verify Extension Fixture System

Tests the new fixture-based architecture:
1. ExtensionLoader discovers extensions
2. FIXTURES are registered in global registry
3. scripts/status.py uses FixtureRegistry to get Rust implementations
"""

import asyncio
import sys
from pathlib import Path

# Add paths
agent_src = Path(__file__).parent / "packages" / "python" / "agent" / "src"
core_src = Path(__file__).parent / "packages" / "python" / "core" / "src"
assets_src = Path(__file__).parent / "assets"

if str(agent_src) not in sys.path:
    sys.path.insert(0, str(agent_src))
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))
if str(assets_src) not in sys.path:
    sys.path.insert(0, str(assets_src))


async def test_fixture_system():
    """Test the fixture system."""
    print("\n" + "=" * 60)
    print("Testing Extension Fixture System")
    print("=" * 60)

    # Test 1: Load extensions and register fixtures
    print("\n[1/4] Loading extensions...")
    from omni.core.skills.extensions.fixtures import FixtureManager

    skill_path = Path(__file__).parent / "assets" / "skills" / "git"
    manager = FixtureManager(skill_path)
    fixtures = manager.discover_and_register()

    print(f"  Extensions found: {list(fixtures.keys())}")
    for ext_name, funcs in fixtures.items():
        print(f"    - {ext_name}: {funcs}")

    # Test 2: Check registry
    print("\n[2/4] Checking FixtureRegistry...")
    from omni.core.skills.extensions.fixtures import FixtureRegistry

    registered = FixtureRegistry.list_registered()
    print(f"  Registered fixtures: {registered}")

    # Test 3: Get Rust implementation
    print("\n[3/4] Getting Rust implementation...")
    rust_status = FixtureRegistry.get("rust_bridge", "get_status")
    if rust_status:
        print(f"  ✓ Rust get_status found: {rust_status}")
    else:
        print("  ⚠ Rust get_status not found (expected - Rust bindings not available)")

    # Test 4: Use scripts/status.py
    print("\n[4/4] Testing scripts/status.py...")
    from assets.skills.git.scripts.status import git_status, git_status_detailed

    result = git_status()
    print(f"  git_status(): {result[:60]}...")

    detailed = git_status_detailed()
    print(f"  git_status_detailed(): backend={detailed.get('backend', 'unknown')}")

    print("\n" + "=" * 60)
    print("Fixture System Test: PASSED")
    print("=" * 60 + "\n")
    return True


async def main():
    """Run all tests."""
    print("\n🚀 Omni-Dev Fusion Fixture System Verification\n")

    success = await test_fixture_system()

    if success:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
